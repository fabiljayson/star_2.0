import '../../core/api_client.dart';
import '../../core/app_session.dart';
import 'notification.dart';

/// Data access for the in-app notification center.
class NotificationsRepository {
  NotificationsRepository(this.session);

  final AppSession session;

  ApiClient get _client => session.api;

  Future<int> unreadCount() async {
    final data = await _client.getJson('notifications/unread-count/');
    if (data is Map<String, dynamic>) {
      final value = data['count'] ?? data['unread'];
      if (value is int) return value;
    }
    return 0;
  }

  Future<List<StarNotification>> list({
    bool unreadOnly = false,
    int pageSize = 50,
  }) async {
    final data = await _client.getJson('notifications/', query: {
      'page_size': '$pageSize',
      if (unreadOnly) 'is_read': 'false',
    });
    if (data is! Map<String, dynamic>) return const [];
    final raw = data['results'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(StarNotification.fromJson)
        .toList();
  }

  Future<void> markRead(String id) =>
      _client.postJson('notifications/$id/read/', body: {});

  Future<void> markAllRead() =>
      _client.postJson('notifications/read-all/', body: {});

  Future<List<NotificationPreference>> preferences() async {
    final data = await _client.getJson('notifications/preferences/');
    if (data is! List) return const [];
    return data
        .whereType<Map<String, dynamic>>()
        .map(NotificationPreference.fromJson)
        .toList();
  }

  Future<List<NotificationPreference>> updatePreferences(
    List<NotificationPreference> preferences,
  ) async {
    final data = await _client.putJson('notifications/preferences/', {
      'preferences': [for (final p in preferences) p.toJson()],
    });
    if (data is! List) return const [];
    return data
        .whereType<Map<String, dynamic>>()
        .map(NotificationPreference.fromJson)
        .toList();
  }
}
