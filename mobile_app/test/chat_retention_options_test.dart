import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/utils/chat_retention_options.dart';

void main() {
  test('options match the backend choices plus forever', () {
    expect(kChatRetentionOptions.map((o) => o.days), [30, 90, 365, null]);
  });

  test('chatRetentionLabel describes each choice', () {
    expect(chatRetentionLabel(30), 'Kept for 30 days');
    expect(chatRetentionLabel(90), 'Kept for 90 days');
    expect(chatRetentionLabel(365), 'Kept for 1 year');
    expect(chatRetentionLabel(null), 'Kept forever');
    expect(chatRetentionLabel(7), 'Kept for 7 days');
  });
}
