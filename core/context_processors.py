def unread_notifications(request):
    if request.user.is_authenticated:
        all_notifs = request.user.notifications.order_by('-created_at')
        unread_notifs = [n for n in all_notifs if not n.is_read]
        return {
            'unread_notifications': unread_notifs,
            'all_notifications': all_notifs
        }
    return {'unread_notifications': [], 'all_notifications': []}