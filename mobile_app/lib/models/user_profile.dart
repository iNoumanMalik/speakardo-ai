import '../utils/chat_retention_options.dart';

class UserProfile {
  final String id;
  final String email;
  final bool emailVerified;
  final String timezone;
  final bool notificationsEnabled;

  /// Days of chat history kept on the server; `null` = forever.
  final int? chatRetentionDays;
  final DateTime createdAt;

  const UserProfile({
    required this.id,
    required this.email,
    required this.emailVerified,
    required this.timezone,
    required this.notificationsEnabled,
    this.chatRetentionDays = kDefaultChatRetentionDays,
    required this.createdAt,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'].toString(),
      email: json['email'] as String,
      emailVerified: json['email_verified'] as bool? ?? true,
      timezone: json['timezone'] as String? ?? 'UTC',
      notificationsEnabled: json['notifications_enabled'] as bool? ?? true,
      // An explicit null means "forever"; a missing key (older backend) the default.
      chatRetentionDays: json.containsKey('chat_retention_days')
          ? json['chat_retention_days'] as int?
          : kDefaultChatRetentionDays,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  UserProfile copyWith({
    bool? emailVerified,
    String? timezone,
    bool? notificationsEnabled,
  }) {
    return UserProfile(
      id: id,
      email: email,
      emailVerified: emailVerified ?? this.emailVerified,
      timezone: timezone ?? this.timezone,
      notificationsEnabled:
          notificationsEnabled ?? this.notificationsEnabled,
      chatRetentionDays: chatRetentionDays,
      createdAt: createdAt,
    );
  }
}
