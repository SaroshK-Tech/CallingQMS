from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from core.models import TicketCall, Advertisement


def full_display(request):
    recent_calls = TicketCall.objects.select_related(
        'ticket', 'ticket__service', 'counter'
    ).order_by('-called_at')[:4]
    
    ads = Advertisement.objects.filter(is_active=True)
    
    return render(request, 'display/full_display.html', {
        'recent_calls': recent_calls,
        'ads': ads,
    })


def api_recent_calls(request):
    calls = TicketCall.objects.select_related(
        'ticket', 'ticket__service', 'counter'
    ).order_by('-called_at')[:4]
    
    data = [{
        'ticket_number': c.ticket.ticket_number,
        'counter_name': c.counter.display_name or c.counter.name,
        'service': c.ticket.service.name,
        'called_at': c.called_at.strftime('%H:%M:%S'),
    } for c in calls]
    
    return JsonResponse({'calls': data})


def api_advertisements(request):
    ads = Advertisement.objects.filter(is_active=True)
    data = [{
        'id': ad.id,
        'title': ad.title,
        'image': ad.image.url if ad.image else None,
        'video': ad.video.url if ad.video else None,
    } for ad in ads]
    return JsonResponse({'advertisements': data})
