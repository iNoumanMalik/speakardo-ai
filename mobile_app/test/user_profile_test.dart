import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/user_profile.dart';

Map<String, dynamic> _json([Map<String, dynamic> extra = const {}]) => {
      'id': 'u1',
      'email': 'user@example.com',
      'email_verified': true,
      'timezone': 'Asia/Karachi',
      'notifications_enabled': true,
      'created_at': '2026-09-26T10:00:00+00:00',
      ...extra,
    };

void main() {
  test('chat retention is parsed from the profile', () {
    final profile = UserProfile.fromJson(_json({'chat_retention_days': 30}));
    expect(profile.chatRetentionDays, 30);
  });

  test('an explicit null means keep forever', () {
    final profile = UserProfile.fromJson(_json({'chat_retention_days': null}));
    expect(profile.chatRetentionDays, isNull);
  });

  test('a missing field (older backend) falls back to 90 days', () {
    expect(UserProfile.fromJson(_json()).chatRetentionDays, 90);
  });

  test('copyWith keeps the retention setting', () {
    final profile = UserProfile.fromJson(_json({'chat_retention_days': null}));
    final updated = profile.copyWith(notificationsEnabled: false);
    expect(updated.chatRetentionDays, isNull);
    expect(updated.notificationsEnabled, isFalse);
  });
}
