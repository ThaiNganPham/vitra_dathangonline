import csv
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import requests

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


def save_order(order):
    """Gửi đơn hàng Vị Trà đến Google Apps Script."""
    import logging

    logger = logging.getLogger("vitra")

    url = secret("APPS_SCRIPT_URL")
    token = secret("ORDER_SECRET")

    if not url or not token:
        raise RuntimeError("Thiếu cấu hình Streamlit Secrets")

    items = json.loads(order["items"])

    payload = {
        "secret": token,
        "items": [
            {
                "name": item["name"],
                "quantity": item["qty"],
                "price": item["price"]
            }
            for item in items
        ],
        "delivery_type": order["method"],
        "address": order["address"],
        "customer_name": order["customer"],
        "phone": order["phone"],
        "payment_method": order["payment"],
        "note": order["note"]
    }

    logger.warning("ViTra: Starting POST request")

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=25,
            allow_redirects=True
        )

        logger.warning(
            "ViTra: HTTP=%s, Content-Type=%s, Redirects=%s",
            response.status_code,
            response.headers.get("Content-Type"),
            len(response.history)
        )

        response.raise_for_status()

        result = response.json()

        if result.get("success") is not True:
            raise RuntimeError(
                "Apps Script error: " +
                str(result.get("error", "Unknown error"))
            )

        if not result.get("orderNo"):
            raise RuntimeError("Apps Script không trả về mã đơn")

        logger.warning("ViTra: Order saved successfully")

        return str(result["orderNo"])

    except requests.exceptions.RequestException as e:
        logger.error(
            "ViTra: Request failed: %s",
            type(e).__name__
        )
        raise

    except ValueError:
        logger.error("ViTra: Invalid JSON response")
        raise RuntimeError("Apps Script không trả về JSON hợp lệ")

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
    st.info('Đơn hàng được lưu trong tab Orders của Google Sheets. Mở Google Sheets để xem và cập nhật trạng thái đơn.')
    st.caption('Trang quản trị đồng bộ trạng thái trực tiếp sẽ được bổ sung ở phiên bản tiếp theo.')

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
            'customer':name.strip(),'phone':re.sub(r'[\s.-]','',phone),
            'method':method,'address':address.strip(),'payment':payment,'note':note.strip(),
            'items':json.dumps([{'id':x['id'],'name':x['name'],'price':x['price'],'qty':q} for x,q in selected],ensure_ascii=False)}
        try:
            order_no = save_order(order)
        except Exception:
            st.error(
                'Không lưu được đơn vào Google Sheets.Vui lòng đừng đặt lại tại không có lưu.\n'
                NÓI CHỨ MỚI LÀM TỚI ĐÂY À')
            return
        st.session_state.cart={}
        st.success(f'Đã gửi đơn {order_no}! Vị Trà sẽ liên hệ xác nhận.')
        if method=='Giao tận nơi':st.info('Phí giao hàng sẽ được quán thông báo khi xác nhận. Tổng tiền hiện tại chưa gồm phí giao.')
        if payment=='Chuyển khoản':st.info('Vui lòng đợi quán xác nhận số tiền và thông tin chuyển khoản trước khi thanh toán.')

page=st.query_params.get('page','order')
if page=='admin':admin()
else:customer()
