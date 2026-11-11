import csv
import io
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

st.set_page_config(page_title='Vị Trà | Đặt nước', page_icon='🍃', layout='centered')
st.markdown('''<style>
.stApp {background:#faf8f2;color:#3c2d24}
h1,h2,h3 {color:#4c3428!important}
.stButton>button[kind="primary"] {background:#52734d;color:white;border:0}
[data-testid="stMetricValue"]{color:#52734d}
</style>''', unsafe_allow_html=True)
ROOT=Path(__file__).parent
TZ=ZoneInfo('Asia/Ho_Chi_Minh')
STATUS=['Mới','Đã xác nhận','Đang pha chế','Sẵn sàng','Đang giao','Hoàn tất','Đã hủy']

def secret(key, default=''):
    try:return st.secrets.get(key, default)
    except Exception:return os.environ.get(key,default)

def sheets():
    if not secret('GOOGLE_SHEET_ID'):return None
    import gspread
    from google.oauth2.service_account import Credentials
    creds=Credentials.from_service_account_info(dict(st.secrets['gcp_service_account']),scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return gspread.authorize(creds).open_by_key(secret('GOOGLE_SHEET_ID'))

def conn():
    c=sqlite3.connect(ROOT/'orders_local.db',timeout=15)
    c.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, created_at TEXT, customer TEXT, phone TEXT, method TEXT, address TEXT, payment TEXT, note TEXT, items TEXT, subtotal INTEGER, shipping INTEGER, total INTEGER, status TEXT)')
    c.commit();return c

COLS=['id','created_at','customer','phone','method','address','payment','note','items','subtotal','shipping','total','status']

def save_order(order):
    sh=sheets()
    if sh:
        try:ws=sh.worksheet('Orders')
        except Exception:ws=sh.add_worksheet(title='Orders',rows=1000,cols=13);ws.append_row(COLS)
        ws.append_row([order.get(k,'') for k in COLS],value_input_option='RAW')
    else:
        with conn() as c:c.execute('INSERT INTO orders VALUES ('+','.join('?'*len(COLS))+')',[order.get(k,'') for k in COLS])

def get_orders():
    sh=sheets()
    if sh:
        try:return sh.worksheet('Orders').get_all_records()
        except Exception:return []
    with conn() as c:return [dict(zip(COLS,r)) for r in c.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()]

def set_status(order_id,status):
    sh=sheets()
    if sh:
        ws=sh.worksheet('Orders'); cell=ws.find(order_id,in_column=1)
        if not cell:raise ValueError('Không tìm thấy đơn')
        ws.update_cell(cell.row,13,status)
    else:
        with conn() as c:c.execute('UPDATE orders SET status=? WHERE id=?',(status,order_id))

@st.cache_data(ttl=30)
def menu():
    with (ROOT/'menu.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    result=[]
    for r in rows:
        try:p=int(float(r['price'])) if r['price'].strip() else 0
        except ValueError:p=0
        if p>0 and r['available'].strip()=='1':result.append({**r,'price':p})
    return result

def vnd(n):return f'{int(n):,}'.replace(',','.')+'đ'

def admin():
    st.title('📋 Quản lý đơn hàng')
    password=secret('ADMIN_PASSWORD')
    if not password:
        st.error('Chưa cấu hình ADMIN_PASSWORD trong Streamlit Secrets.');return
    if not st.session_state.get('admin_ok'):
        with st.form('login'):
            p=st.text_input('Mật khẩu quản trị',type='password')
            if st.form_submit_button('Đăng nhập'):
                import hmac
                if hmac.compare_digest(p,password):st.session_state.admin_ok=True;st.rerun()
                else:st.error('Sai mật khẩu')
        return
    if st.button('Đăng xuất'):st.session_state.admin_ok=False;st.rerun()
    a,b=st.tabs(['Đơn hàng','Menu và giá'])
    with a:
        if st.button('🔄 Làm mới'):st.rerun()
        orders=get_orders()
        if not orders:st.info('Chưa có đơn hàng')
        for o in sorted(orders,key=lambda x:str(x['created_at']),reverse=True):
            with st.expander(f"{o['id']} · {o['customer']} · {vnd(o['total'])} · {o['status']}"):
                st.write(f"🕒 {o['created_at']} | 📞 {o['phone']}")
                st.write(f"Nhận hàng: {o['method']} · {o['address']}")
                st.write(f"Thanh toán: {o['payment']} · Phí giao: {vnd(o['shipping'])}")
                st.write(f"Ghi chú: {o['note'] or 'Không có'}")
                for item in json.loads(o['items']):st.write(f"• {item['name']} × {item['qty']} — {vnd(item['price']*item['qty'])}")
                ix=STATUS.index(o['status']) if o['status'] in STATUS else 0
                status=st.selectbox('Trạng thái',STATUS,index=ix,key='status_'+o['id'])
                if st.button('Lưu trạng thái',key='save_'+o['id']):
                    try:set_status(o['id'],status);st.success('Đã cập nhật');st.rerun()
                    except Exception as e:st.error(f'Lỗi cập nhật: {e}')
    with b:
        st.warning('Menu lưu trong menu.csv. Trên Streamlit Cloud, chỉnh sửa tại GitHub để thay đổi được giữ lâu dài.')
        df=pd.read_csv(ROOT/'menu.csv',dtype=str,keep_default_na=False)
        edited=st.data_editor(df,hide_index=True,num_rows='fixed',use_container_width=True)
        st.download_button('Tải menu.csv đã chỉnh',edited.to_csv(index=False).encode('utf-8-sig'),'menu.csv','text/csv')
        st.caption('Điền giá bằng VND (ví dụ 35000). Món chưa có giá sẽ không hiện cho khách. Đặt available = 0 để ẩn món.')

def customer():
    st.title('🍃 VỊ TRÀ')
    st.caption('Trà • Trà sữa • Cà phê | Bảo Lộc')
    st.subheader('Đặt nước online')
    items=menu()
    if not items:
        st.info('Quán đang cập nhật menu và giá. Vui lòng quay lại sau.');return
    if 'cart' not in st.session_state:st.session_state.cart={}
    search=st.text_input('🔎 Tìm món nước',placeholder='Ví dụ: Oolong, cà phê...')
    groups=list(dict.fromkeys(x['group'] for x in items))
    chosen=st.selectbox('Danh mục',['Tất cả']+groups)
    filtered=[x for x in items if (chosen=='Tất cả' or x['group']==chosen) and search.casefold() in x['name'].casefold()]
    for item in filtered:
        left,right=st.columns([3,1])
        with left:
            st.markdown(f"**{item['name']}**")
            st.caption(f"{item['group']} · {vnd(item['price'])}")
        with right:
            if st.button('＋ Thêm',key='add_'+item['id']):
                st.session_state.cart[item['id']]=st.session_state.cart.get(item['id'],0)+1
                st.rerun()
        st.divider()
    st.subheader('🛒 Giỏ hàng')
    selected=[(x,st.session_state.cart.get(x['id'],0)) for x in items if st.session_state.cart.get(x['id'],0)>0]
    if not selected:st.info('Chọn món để bắt đầu đặt hàng');return
    for item,qty in selected:
        a,b=st.columns([3,1]);a.write(f"{item['name']} — {vnd(qty*item['price'])}")
        b.number_input('Số lượng',min_value=0,max_value=50,value=qty,step=1,key='qty_'+item['id'],on_change=None,label_visibility='collapsed')
    if st.button('Cập nhật số lượng'):
        for item,_ in selected:st.session_state.cart[item['id']]=st.session_state['qty_'+item['id']]
        st.rerun()
    subtotal=sum(x['price']*q for x,q in selected)
    st.metric('Tiền nước',vnd(subtotal))
    with st.form('checkout',clear_on_submit=False):
        name=st.text_input('Tên người nhận *')
        phone=st.text_input('Số điện thoại *')
        method=st.radio('Hình thức nhận', ['Nhận tại quán','Giao tận nơi'])
        address=st.text_area('Địa chỉ giao hàng *' if method=='Giao tận nơi' else 'Ghi chú vị trí nhận (không bắt buộc)')
        payment=st.radio('Thanh toán',['Tiền mặt','Chuyển khoản'])
        note=st.text_area('Ghi chú đơn hàng',placeholder='Ít đá, ít ngọt, thời gian nhận...')
        st.caption('Phí giao hàng chưa được tính tự động; quán sẽ xác nhận phí giao trước khi xử lý đơn.')
        st.markdown(f'**Tạm tính: {vnd(subtotal)} + phí giao hàng (nếu có)**')
        submitted=st.form_submit_button('Xác nhận đặt nước',type='primary',use_container_width=True)
    if submitted:
        if not name.strip() or not re.fullmatch(r'0\d{9,10}',re.sub(r'[\s.-]','',phone)):
            st.error('Vui lòng nhập tên và số điện thoại Việt Nam hợp lệ.');return
        if method=='Giao tận nơi' and len(address.strip())<8:
            st.error('Vui lòng nhập địa chỉ giao hàng đầy đủ.');return
        if not st.session_state.cart or subtotal<=0:st.error('Giỏ hàng trống.');return
        order={
            'id':'VT-'+datetime.now(TZ).strftime('%y%m%d')+'-'+uuid.uuid4().hex[:6].upper(),
            'created_at':datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S'),
            'customer':name.strip(),'phone':re.sub(r'[\s.-]','',phone),
            'method':method,'address':address.strip(),'payment':payment,'note':note.strip(),
            'items':json.dumps([{'id':x['id'],'name':x['name'],'price':x['price'],'qty':q} for x,q in selected],ensure_ascii=False),
            'subtotal':subtotal,'shipping':0,'total':subtotal,'status':'Mới'}
        try:
            save_order(order)
        except Exception as e:
            st.error('Chưa gửi được đơn. Vui lòng thử lại hoặc liên hệ quán.');return
        st.session_state.cart={}
        st.success(f"Đã gửi đơn {order['id']}! Vị Trà sẽ liên hệ xác nhận.")
        if method=='Giao tận nơi':st.info('Phí giao hàng sẽ được quán thông báo khi xác nhận. Tổng tiền hiện tại chưa gồm phí giao.')
        if payment=='Chuyển khoản':st.info('Vui lòng đợi quán xác nhận số tiền và thông tin chuyển khoản trước khi thanh toán.')

page=st.query_params.get('page','order')
if page=='admin':admin()
else:customer()
