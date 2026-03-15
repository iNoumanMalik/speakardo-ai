import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://127.0.0.1:8000'; // local FastAPI

  // Send message to get parsed reminder and confirmation text
  Future<Map<String, dynamic>> sendMessage(String message) async {
    final response = await http.post(
      Uri.parse('$baseUrl/chat'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'message': message}),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to send message: ${response.statusCode}');
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
