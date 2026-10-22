"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from orders import views as order_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Separated Page Views
    path('', order_views.index_view, name='workstation-home'),
    path('workstation/', order_views.workstation_page_view, name='workstation-page'),
    path('orders/', order_views.orders_page_view, name='orders-page'),
    path('boxes/', order_views.boxes_page_view, name='boxes-page'),
    path('history/', order_views.history_page_view, name='history-page'),
    path('ai/', order_views.ai_page_view, name='ai-page'),
    # API Endpoints
    path('api/orders/', order_views.api_list_orders, name='api-orders'),
    path('api/orders/create/', order_views.api_create_order, name='api-order-create'),
    path('api/orders/<str:order_number>/update/', order_views.api_update_order, name='api-order-update'),
    path('api/recommendation/<str:order_number>/', order_views.api_recommend_box, name='api-recommendation'),
    path('api/reserve/', order_views.api_reserve_box, name='api-reserve'),
    path('api/chat/', order_views.api_chat, name='api-chat'),
    path('api/boxes/', order_views.api_list_boxes, name='api-boxes'),
    path('api/boxes/create/', order_views.api_create_box, name='api-box-create'),
    path('api/boxes/<str:code>/update/', order_views.api_update_box, name='api-box-update'),
    path('api/products/', order_views.api_list_products, name='api-products'),
    path('api/history/', order_views.api_list_history, name='api-history'),
]
