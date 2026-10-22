from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'sku',
        'name',
        'dimensions_display',
        'weight_display',
        'clearance_display',
        'is_fragile',
        'is_active',
        'updated_at',
    )
    list_filter = ('is_active', 'is_fragile')
    search_fields = ('sku', 'name')
    readonly_fields = ('created_at', 'updated_at', 'calculated_volume', 'effective_dimensions_display')

    fieldsets = (
        ('Product Identification', {
            'fields': ('sku', 'name', 'is_active', 'is_fragile')
        }),
        ('Physical Specifications (Verified Catalog Data)', {
            'fields': (
                ('length', 'width', 'height'),
                'weight',
                'clearance',
                'calculated_volume',
                'effective_dimensions_display',
            ),
            'description': 'Dimensions are in centimetres (cm). Weight is in kilograms (kg). Clearance is applied on each side.'
        }),
        ('Audit Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Dimensions (L x W x H cm)')
    def dimensions_display(self, obj):
        return f"{obj.length} × {obj.width} × {obj.height} cm"

    @admin.display(description='Weight (kg)')
    def weight_display(self, obj):
        return f"{obj.weight} kg"

    @admin.display(description='Clearance (cm/side)')
    def clearance_display(self, obj):
        return f"+{obj.clearance} cm"

    @admin.display(description='Raw Volume (cm³)')
    def calculated_volume(self, obj):
        return f"{obj.volume:.2f} cm³"

    @admin.display(description='Effective Dimensions with Clearance (cm)')
    def effective_dimensions_display(self, obj):
        el, ew, eh = obj.effective_dimensions
        return f"{el:.2f} × {ew:.2f} × {eh:.2f} cm (Vol: {obj.effective_volume:.2f} cm³)"
