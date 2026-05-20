from .models import Notification

def notifications_processor(request):
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user, status='pending').order_by('-created_at')[:5]
        unread_count = Notification.objects.filter(user=request.user, status='pending').count()
        return {
            'recent_notifications': unread_notifications,
            'unread_notifications_count': unread_count,
        }
    return {}
