from .models import Cart

def cart_total(request):
    cart_count = 0
    cart_total_price = 0
    cart = None
    
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    else:
        session_key = request.session.session_key
        if session_key:
            cart = Cart.objects.filter(session_key=session_key).first()
    
    if cart:
        cart_count = cart.get_total_items()
        cart_total_price = cart.get_total_price()
    
    return {
        'cart_count': cart_count,
        'cart_total_price': cart_total_price,
    }