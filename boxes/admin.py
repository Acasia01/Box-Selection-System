from django.contrib import admin
from .models import BoxType, BoxInventory


class BoxInventoryInline(admin.StackedInline):
    model = BoxInventory
    can_delete = False
    verbose_name = 'Inventory Stock'
    verbose_name_plural = 'Inventory Stock'
    fields = ('quantity_on_hand', 'quantity_reserved', 'quantity_available_display')
    readonly_fields = ('quantity_available_display',)

    @admin.display(description='Available Quantity (On Hand - Reserved)')
    def quantity_available_display(self, obj):
        return obj.quantity_available if obj else 0


@admin.register(BoxType)
class BoxTypeAdmin(admin.ModelAdmin):
    inlines = [BoxInventoryInline]
    list_display = (
        'code',
        'name',
        'dimensions_display',
        'max_weight_display',
        'empty_weight_display',
        'cost_display',
        'available_stock_display',
        'is_active',
    )
    list_filter = ('is_active', 'currency')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at', 'internal_volume_display')

    fieldsets = (
        ('Box Identification', {
            'fields': ('code', 'name', 'is_active')
        }),
        ('Internal Dimensions (cm)', {
            'fields': (
                ('length', 'width', 'height'),
                'internal_volume_display',
            ),
            'description': 'Internal dimensions in centimetres (cm). These represent the usable interior space.'
        }),
        ('Weight Capacities (kg)', {
            'fields': (
                ('max_weight', 'empty_weight'),
            ),
            'description': 'Total packed weight cannot exceed max_weight. Empty weight is added to packed weight.'
        }),
        ('Costing', {
            'fields': (('cost', 'currency'),)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Internal (L × W × H cm)')
    def dimensions_display(self, obj):
        return f"{obj.length} × {obj.width} × {obj.height} cm"

    @admin.display(description='Max Packed (kg)')
    def max_weight_display(self, obj):
        return f"{obj.max_weight} kg"

    @admin.display(description='Empty Box (kg)')
    def empty_weight_display(self, obj):
        return f"{obj.empty_weight} kg"

    @admin.display(description='Cost')
    def cost_display(self, obj):
        return f"{obj.currency} {obj.cost:.2f}"

    @admin.display(description='Available Stock')
    def available_stock_display(self, obj):
        if hasattr(obj, 'inventory'):
            avail = obj.inventory.quantity_available
            return f"{avail} units (Stock: {obj.inventory.quantity_on_hand}, Rsv: {obj.inventory.quantity_reserved})"
        return "No inventory record"

    @admin.display(description='Internal Volume (cm³)')
    def internal_volume_display(self, obj):
        return f"{obj.internal_volume:.2f} cm³"


@admin.register(BoxInventory)
class BoxInventoryAdmin(admin.ModelAdmin):
    list_display = (
        'box_type',
        'quantity_on_hand',
        'quantity_reserved',
        'quantity_available',
        'updated_at',
    )
    list_filter = ('box_type__is_active',)
    search_fields = ('box_type__code', 'box_type__name')
    readonly_fields = ('quantity_available', 'updated_at')

    @admin.display(description='Available Quantity')
    def quantity_available(self, obj):
        return obj.quantity_available
