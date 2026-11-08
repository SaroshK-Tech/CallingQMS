from django.contrib import admin

from .models import (
    Advertisement,
    Counter,
    CounterService,
    CounterUser,
    Feedback,
    Service,
    Ticket,
    TicketCall,
)


class CounterServiceInline(admin.TabularInline):
    model = CounterService
    extra = 1
    ordering = ['sequence']


class ServiceCounterInline(admin.TabularInline):
    """Assign an exceptional category to one or several counters."""

    model = CounterService
    fk_name = 'service'
    extra = 1
    ordering = ['sequence']
    verbose_name = 'Assigned counter'
    verbose_name_plural = 'Assigned counters'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'prefix', 'is_usual', 'is_active']
    list_filter = ['is_usual', 'is_active']
    list_editable = ['is_usual', 'is_active']
    search_fields = ['name', 'prefix']
    inlines = [ServiceCounterInline]


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


@admin.register(CounterService)
class CounterServiceAdmin(admin.ModelAdmin):
    list_display = ['counter', 'service', 'sequence']
    list_filter = ['service', 'counter']
    ordering = ['counter', 'sequence']


@admin.register(CounterUser)
class CounterUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'counter']
    list_filter = ['counter']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'service', 'status', 'current_counter',
        'no_show_count', 'created_at',
    ]
    list_filter = ['status', 'service', 'current_counter']
    search_fields = ['ticket_number']


@admin.register(TicketCall)
class TicketCallAdmin(admin.ModelAdmin):
    list_display = [
        'ticket', 'counter', 'called_at', 'served', 'served_at',
        'duration_seconds', 'no_show', 'recall_count',
    ]
    list_filter = ['counter', 'served', 'no_show', 'recalled']
    search_fields = ['ticket__ticket_number']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'counter', 'rating', 'source', 'created_at']
    list_filter = ['rating', 'source', 'counter']
    search_fields = ['ticket__ticket_number', 'comment']


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'order']
    list_filter = ['is_active']
