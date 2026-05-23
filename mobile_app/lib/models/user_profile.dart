class UserProfile {
  final String id;
  final String email;
  final String timezone;
  final bool notificationsEnabled;
  final DateTime createdAt;

  const UserProfile({
    required this.id,
    required this.email,
    required this.timezone,
    required this.notificationsEnabled,
    required this.createdAt,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'].toString(),
      email: json['email'] as String,
      timezone: json['timezone'] as String? ?? 'UTC',
      notificationsEnabled: json['notifications_enabled'] as bool? ?? true,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  UserProfile copyWith({
    String? timezone,
    bool? notificationsEnabled,
  }) {
    return UserProfile(
      id: id,
      email: email,
      timezone: timezone ?? this.timezone,
      notificationsEnabled:
          notificationsEnabled ?? this.notificationsEnabled,
      createdAt: createdAt,
    );
  }
}
