from django.contrib import admin
from .models import Order, OrderItem, RecommendationRun, RecommendationCandidate


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ('product', 'quantity', 'item_weight_display', 'item_volume_display')
    readonly_fields = ('item_weight_display', 'item_volume_display')

    @admin.display(description='Total Weight (kg)')
    def item_weight_display(self, obj):
        return f"{obj.total_weight:.3f} kg" if obj and obj.product else "-"

    @admin.display(description='Total Eff. Volume (cm³)')
    def item_volume_display(self, obj):
        return f"{(obj.product.effective_volume * obj.quantity):.2f} cm³" if obj and obj.product else "-"


class RecommendationCandidateInline(admin.TabularInline):
    model = RecommendationCandidate
    extra = 0
    can_delete = False
    fields = (
        'rank',
        'box_type',
        'is_eligible',
        'cost',
        'total_packed_weight',
        'unused_volume',
        'explanation',
    )
    readonly_fields = (
        'rank',
        'box_type',
        'is_eligible',
        'cost',
        'total_packed_weight',
        'unused_volume',
        'explanation',
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = (
        'order_number',
        'customer_name',
        'status',
        'total_items_display',
        'total_weight_display',
        'assigned_box',
        'is_assigned',
        'created_at',
    )
    list_filter = ('status', 'is_assigned', 'created_at')
    search_fields = ('order_number', 'customer_name')
    readonly_fields = ('created_at', 'updated_at', 'assigned_at')

    @admin.display(description='Total Items')
    def total_items_display(self, obj):
        return obj.total_items_quantity

    @admin.display(description='Total Weight (kg)')
    def total_weight_display(self, obj):
        return f"{obj.total_weight:.3f} kg"


@admin.register(RecommendationRun)
class RecommendationRunAdmin(admin.ModelAdmin):
    inlines = [RecommendationCandidateInline]
    list_display = (
        'id',
        'order',
        'is_successful',
        'best_box',
        'algorithm_version',
        'requester',
        'total_items_count',
        'created_at',
    )
    list_filter = ('is_successful', 'algorithm_version', 'created_at')
    search_fields = ('order__order_number', 'requester', 'summary')
    readonly_fields = (
        'order',
        'algorithm_version',
        'requester',
        'is_successful',
        'best_box',
        'total_items_count',
        'total_products_weight',
        'protective_material_weight',
        'summary',
        'created_at',
    )


@admin.register(RecommendationCandidate)
class RecommendationCandidateAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'run',
        'box_type',
        'is_eligible',
        'rank',
        'cost',
        'total_packed_weight',
    )
    list_filter = ('is_eligible', 'rank')
    search_fields = ('run__order__order_number', 'box_type__code')
