import 'dart:convert';

import '../config/app_config.dart';
import 'auth_http.dart';

class FeedbackService {
  static final String _baseUrl = AppConfig.baseUrl;

  /// Submits in-app feedback. Backend logs it for now; delivery TBD.
  Future<void> submitFeedback(String message) async {
    final response = await AuthHttp.postJson(
      Uri.parse('$_baseUrl/users/me/feedback'),
      {'message': message.trim()},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to submit feedback');
    }

    jsonDecode(response.body);
  }
}
