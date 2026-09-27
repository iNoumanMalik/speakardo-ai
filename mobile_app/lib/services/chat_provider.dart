import 'package:flutter/material.dart';
import '../models/memory_action.dart';
import '../models/message.dart';
import 'api_service.dart';
import 'package:intl/intl.dart';
// import 'tts_service.dart';
import '../utils/repeat_options.dart';

class ChatProvider with ChangeNotifier {
  ChatProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  final ApiService _apiService;
  final List<Message> _messages = [];
  bool _isLoading = false;

  /// Server history (GET /chat/history), loaded newest page first.
  bool _isHistoryLoading = false;
  bool _hasMoreHistory = false;
  String? _nextBefore;

  /// Bumped by [clear] so a history request that finishes after a logout is ignored.
  int _historyGeneration = 0;

  /// Last assistant draft for Phase 2 (clarification, time follow-up, edit-in-chat).
  Map<String, dynamic>? _pendingContext;
  // bool _voiceFeedbackEnabled = true;

  List<Message> get messages => _messages;
  bool get isLoading => _isLoading;
  bool get isHistoryLoading => _isHistoryLoading;
  bool get hasMoreHistory => _hasMoreHistory;

  /// Forget the conversation held in memory (another user may be signing in).
  void clear() {
    _historyGeneration++;
    _messages.clear();
    _pendingContext = null;
    _isHistoryLoading = false;
    _hasMoreHistory = false;
    _nextBefore = null;
    notifyListeners();
  }

  /// Loads the newest page of stored messages. Messages sent while it loads
  /// stay in front of the restored ones.
  Future<void> loadHistory() => _loadHistoryPage(before: null);

  /// Loads the next older page, if any. Overlapping calls are ignored.
  Future<void> loadOlder() async {
    if (!_hasMoreHistory || _nextBefore == null) return;
    await _loadHistoryPage(before: _nextBefore);
  }

  Future<void> _loadHistoryPage({required String? before}) async {
    if (_isHistoryLoading) return;
    final generation = _historyGeneration;
    _isHistoryLoading = true;
    notifyListeners();
    try {
      final page = await _apiService.getChatHistory(before: before);
      if (generation != _historyGeneration) return;
      _appendHistoryPage(page);
    } catch (e) {
      debugPrint('ChatProvider: history load failed: $e');
    } finally {
      if (generation == _historyGeneration) {
        _isHistoryLoading = false;
        notifyListeners();
      }
    }
  }

  void _appendHistoryPage(Map<String, dynamic> page) {
    final known = _messages.map((m) => m.id).whereType<String>().toSet();
    final rows = page['messages'] as List<dynamic>? ?? const [];
    for (final row in rows) {
      final message = Message.fromHistoryJson(row as Map<String, dynamic>);
      if (message.id != null && known.contains(message.id)) continue;
      // _messages is newest first, so older history goes at the end.
      _messages.add(message);
    }
    _hasMoreHistory = page['has_more'] == true;
    _nextBefore = page['next_before']?.toString();
  }
  // bool get voiceFeedbackEnabled => _voiceFeedbackEnabled;

  // void setVoiceFeedbackEnabled(bool enabled) {
  //   _voiceFeedbackEnabled = enabled;
  //   if (!enabled) {
  //     TtsService.stop();
  //   }
  //   notifyListeners();
  // }

  void addMessage(Message message) {
    _messages.insert(0, message);
    notifyListeners();
  }

  void _addAssistantMessage(
    String displayText, {
    List<MemoryAction> memoryActions = const [],
  }) {
    addMessage(
      Message(
        text: displayText,
        isUser: false,
        timestamp: DateTime.now(),
        memoryActions: memoryActions,
      ),
    );
    // TTS disabled — was: speak [ttsPhrase] for reminder confirmations / prompts.
    // if (ttsPhrase != null &&
    //     ttsPhrase.trim().isNotEmpty &&
    //     _voiceFeedbackEnabled) {
    //   TtsService.speak(ttsPhrase.trim());
    // }
  }

  // TTS disabled — short spoken lines for reminder draft replies.
  // String _shortTtsForDraftReply(
  //   String reply,
  //   Map<String, dynamic> draft,
  // ) {
  //   final confirmable = draft['confirmable'];
  //   if (confirmable == true) {
  //     if (draft['edit_reminder_id'] != null) {
  //       return 'Should I update this reminder? Tap yes or no.';
  //     }
  //     return 'Should I save this reminder? Tap yes or no.';
  //   }
  //   final time = draft['time'];
  //   final hasTime = time != null && time.toString().trim().isNotEmpty;
  //   if (!hasTime) {
  //     return 'What time should I remind you?';
  //   }
  //   if (reply.toLowerCase().contains('couldn\'t match') ||
  //       reply.toLowerCase().contains("couldn't match")) {
  //     return 'I could not match that to a saved reminder.';
  //   }
  //   return 'One quick question.';
  // }

  void _clearPendingReminderFor(Map<String, dynamic> reminderData) {
    final int idx = _messages.indexWhere(
      (m) =>
          !m.isUser &&
          m.pendingReminder != null &&
          identical(m.pendingReminder, reminderData),
    );
    if (idx != -1) {
      _messages[idx] = _messages[idx].copyWith(clearPendingReminder: true);
    }
  }

  Future<void> sendMessage(String text) async {
    addMessage(Message(
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    ));

    _isLoading = true;
    notifyListeners();

    try {
      final response = await _apiService.sendMessage(
        text,
        pendingContext: _pendingContext,
      );

      final reply = response['reply'] as String? ?? '';
      final parsedReminder = response['parsed_reminder'];
      final memoryActions = _memoryActionsFrom(response);

      if (parsedReminder is Map) {
        final draft = Map<String, dynamic>.from(parsedReminder);
        _pendingContext = draft;
        addMessage(Message(
          text: reply,
          isUser: false,
          timestamp: DateTime.now(),
          pendingReminder: draft,
          memoryActions: memoryActions,
        ));
        // TTS disabled — was: TtsService.speak(_shortTtsForDraftReply(...))
      } else {
        _pendingContext = null;
        _addAssistantMessage(reply, memoryActions: memoryActions);
        // TTS disabled — was: spoken greeting / error lines for hello & parse failures.
      }
    } catch (e) {
      _addAssistantMessage('Error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  List<MemoryAction> _memoryActionsFrom(Map<String, dynamic> response) {
    final raw = response['memory_actions'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((a) => MemoryAction.fromJson(Map<String, dynamic>.from(a)))
        .toList();
  }

  /// Undo from a memory chip ("Saved · Undo"). Returns false if it failed.
  Future<bool> undoMemoryAction(Message message, MemoryAction action) async {
    if (!action.canUndo) return false;
    try {
      await _apiService.undoMemory(action.memoryId!);
    } catch (e) {
      debugPrint('ChatProvider: undo failed: $e');
      return false;
    }
    final index = _messages.indexWhere((m) => identical(m, message));
    if (index != -1) {
      final updated = [
        for (final a in message.memoryActions)
          identical(a, action) ? a.markUndone() : a,
      ];
      _messages[index] = message.copyWith(memoryActions: updated);
      notifyListeners();
    }
    return true;
  }

  Future<bool> confirmReminder(Map<String, dynamic> reminderData) async {
    if (reminderData['confirmable'] == false) {
      return false;
    }

    _isLoading = true;
    notifyListeners();

    try {
      final String task = reminderData['task'] ?? 'No Task';
      final String date =
          reminderData['date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
      final String time = reminderData['time'] ?? '00:00';
      final String? repeat = reminderData['repeat'] as String?;
      final editId = reminderData['edit_reminder_id']?.toString();

      final normalizedTime = time.length == 5 ? '$time:00' : time;
      final DateTime local = DateTime.parse('${date}T$normalizedTime');

      final repeatLabel = repeatDisplayLabel(repeat);
      final repeatNote =
          repeatLabel != null ? ' Repeats $repeatLabel.' : '';

      if (editId != null && editId.isNotEmpty) {
        await _apiService.patchReminder(editId, {
          'task': task,
          'datetime': local.toUtc().toIso8601String(),
          'repeat': normalizeRepeatValue(repeat),
        });
        _clearPendingReminderFor(reminderData);
        _pendingContext = null;
        _addAssistantMessage(
          'Reminder updated: "$task" on $date at $time.$repeatNote',
        );
      } else {
        await _apiService.createReminder({
          'task': task,
          'datetime': local.toUtc().toIso8601String(),
          'repeat': normalizeRepeatValue(repeat),
        });
        _clearPendingReminderFor(reminderData);
        _pendingContext = null;
        _addAssistantMessage(
          "Reminder saved! I'll remind you to $task on $date at $time.$repeatNote",
        );
      }
      return true;
    } catch (e) {
      _addAssistantMessage(
        reminderData['edit_reminder_id'] != null
            ? 'Failed to update reminder: $e'
            : 'Failed to save reminder: $e',
      );
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void rejectReminder(Map<String, dynamic> reminderData) {
    _clearPendingReminderFor(reminderData);
    _pendingContext = null;
    _addAssistantMessage(
      'No problem. Please tell me the reminder again with updated details '
      '(for example: \'Remind me to take medicine at 12 PM\').',
    );
    notifyListeners();
  }
}
