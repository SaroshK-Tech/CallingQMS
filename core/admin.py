from django.contrib import admin
from .models import Service, Counter, CounterService, CounterUser, Ticket, TicketCall, Advertisement


class CounterServiceInline(admin.TabularInline):
    model = CounterService
    extra = 1
    ordering = ['sequence']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'prefix', 'is_active']
    list_filter = ['is_active']


@admin.register(Counter)
class CounterAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active']
    list_filter = ['is_active']
    inlines = [CounterServiceInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            from generate_audio import regenerate_counter_audio
            regenerate_counter_audio(obj.id)
            self.message_user(request, f"Audio generated for '{obj.display_name or obj.name}'")
        except Exception as e:
            self.message_user(
                request,
                f"Counter saved but audio regeneration failed (check internet): {e}",
                level='WARNING',
            )


@admin.register(CounterUser)
class CounterUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'counter']
    list_filter = ['counter']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'service', 'status', 'current_counter', 'created_at']
    list_filter = ['status', 'service', 'current_counter']
    search_fields = ['ticket_number']


@admin.register(TicketCall)
class TicketCallAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'counter', 'called_at', 'recalled']
    list_filter = ['counter', 'recalled']


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'order']
    list_filter = ['is_active']
