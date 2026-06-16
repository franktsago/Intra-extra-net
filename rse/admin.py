from django.contrib import admin

from .models import RSEIndicator, RSEInitiative, RSEReport, RSEResource, RSESupplier

admin.site.register(RSEIndicator)
admin.site.register(RSEInitiative)
admin.site.register(RSEReport)
admin.site.register(RSEResource)
admin.site.register(RSESupplier)
