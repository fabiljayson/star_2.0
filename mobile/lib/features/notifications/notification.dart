/// Notifications and per-category preference switches.
class StarNotification {
  StarNotification({
    required this.id,
    required this.category,
    required this.title,
    required this.body,
    required this.link,
    required this.objectType,
    required this.isRead,
    required this.createdAt,
    this.actorName,
  });

  final String id;
  final String category;
  final String title;
  final String body;
  final String link;
  final String objectType;
  final bool isRead;
  final String createdAt;
  final String? actorName;

  factory StarNotification.fromJson(Map<String, dynamic> json) =>
      StarNotification(
        id: '${json['id']}',
        category: '${json['category'] ?? ''}',
        title: (json['title'] ?? '') as String,
        body: (json['body'] ?? '') as String,
        link: '${json['link'] ?? ''}',
        objectType: (json['object_type'] ?? '').toString(),
        isRead: json['is_read'] == true,
        createdAt: '${json['created_at'] ?? ''}',
        actorName: json['actor_detail'] == null
            ? null
            : (json['actor_detail']['full_name'] ??
                    json['actor_detail']['email'] ??
                    '')
                .toString(),
      );
}

/// Per-category switches for the notification center.
class NotificationPreference {
  const NotificationPreference({
    required this.category,
    required this.inApp,
    required this.email,
  });

  final String category;
  final bool inApp;
  final bool email;

  NotificationPreference copyWith({bool? inApp, bool? email}) =>
      NotificationPreference(
        category: category,
        inApp: inApp ?? this.inApp,
        email: email ?? this.email,
      );

  factory NotificationPreference.fromJson(Map<String, dynamic> json) =>
      NotificationPreference(
        category: '${json['category'] ?? ''}',
        inApp: json['in_app'] != false,
        email: json['email'] == true,
      );

  Map<String, dynamic> toJson() =>
      {'category': category, 'in_app': inApp, 'email': email};
}
