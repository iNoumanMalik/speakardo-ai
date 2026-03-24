import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';

class ApiService {
  static final String baseUrl = AppConfig.baseUrl; // Dynamic based on platform


  /// Phase 2: optional [pendingContext] and [recentReminders] for clarification + edits.
  Future<Map<String, dynamic>> sendMessage(
    String message, {
    Map<String, dynamic>? pendingContext,
    List<Map<String, dynamic>>? recentReminders,
  }) async {
    final body = <String, dynamic>{'message': message};
    if (pendingContext != null && pendingContext.isNotEmpty) {
      body['pending_context'] = pendingContext;
    }
    if (recentReminders != null && recentReminders.isNotEmpty) {
      body['recent_reminders'] = recentReminders;
    }

    final response = await http.post(
      Uri.parse('$baseUrl/chat'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('Failed to send message: ${response.statusCode}');
    }
  }

  Future<void> patchReminder(String id, Map<String, dynamic> reminderData) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/reminders/$id'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(reminderData),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update reminder: ${response.statusCode}');
    }
  }

  // Create a reminder after confirmation
  Future<void> createReminder(Map<String, dynamic> reminderData) async {
    final response = await http.post(
      Uri.parse('$baseUrl/reminders'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(reminderData),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to create reminder: ${response.statusCode}');
    }
  }

  // Fetch all reminders
  Future<List<dynamic>> getReminders() async {
    final response = await http.get(Uri.parse('$baseUrl/reminders'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load reminders');
    }
  }

  // Complete reminder
  Future<void> completeReminder(String id) async {
    final response = await http.patch(
      Uri.parse('$baseUrl/reminders/$id/complete'),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update reminder');
    }
  }

  // Delete reminder
  Future<void> deleteReminder(String id) async {
    final response = await http.delete(
      Uri.parse('$baseUrl/reminders/$id'),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to delete reminder');
    }
  }
}
