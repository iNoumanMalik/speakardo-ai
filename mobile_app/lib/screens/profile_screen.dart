import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/auth_provider.dart';
import '../services/feedback_service.dart';
import '../services/profile_provider.dart';
// Timezone UI hidden (Option A). Kept for future use:
// import '../utils/timezone_options.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final FeedbackService _feedbackService = FeedbackService();
  PackageInfo? _packageInfo;
  bool _isSubmittingFeedback = false;

  @override
  void initState() {
    super.initState();
    _loadPackageInfo();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ProfileProvider>().fetchProfile();
    });
  }

  Future<void> _loadPackageInfo() async {
    final info = await PackageInfo.fromPlatform();
    if (!mounted) return;
    setState(() => _packageInfo = info);
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Theme.of(context).colorScheme.error,
      ),
    );
  }

  void _showSuccess(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  Future<void> _showFeedbackForm() async {
    final controller = TextEditingController();

    final submitted = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Send feedback'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Tell us what you like or what we should improve.',
                  style: TextStyle(color: Colors.grey.shade700),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: controller,
                  maxLines: 5,
                  maxLength: 2000,
                  decoration: const InputDecoration(
                    hintText: 'Your feedback...',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                if (controller.text.trim().length < 3) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Please enter at least 3 characters.'),
                    ),
                  );
                  return;
                }
                Navigator.pop(context, true);
              },
              child: const Text('Submit'),
            ),
          ],
        );
      },
    );

    if (submitted != true || !mounted) return;

    setState(() => _isSubmittingFeedback = true);
    try {
      await _feedbackService.submitFeedback(controller.text);
      if (!mounted) return;
      _showSuccess('Thanks! Your feedback was submitted.');
    } catch (_) {
      if (!mounted) return;
      _showError('Could not submit feedback. Please try again.');
    } finally {
      controller.dispose();
      if (mounted) {
        setState(() => _isSubmittingFeedback = false);
      }
    }
  }

  // FAQ removed in favor of in-app feedback.

  Future<void> _contactSupport() async {
    final uri = Uri(
      scheme: 'mailto',
      path: 'support@aireminder.app',
      query: 'subject=AI Reminder App Support',
    );
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      _showError('Could not open email app.');
    }
  }

  // Timezone picker hidden (Option A — device local time for reminders).
  // Kept for when profile timezone is wired end-to-end.
  /*
  Future<void> _pickTimezone(ProfileProvider provider) async {
    final options = timezoneOptionsFor(provider.timezone);
    ...
  }
  */

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w700,
          color: Color(0xFF6750A4),
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        centerTitle: true,
      ),
      body: Consumer<ProfileProvider>(
        builder: (context, provider, _) {
          if (provider.isLoading && provider.profile == null) {
            return const Center(child: CircularProgressIndicator());
          }

          if (provider.profile == null) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    provider.error ?? 'Could not load profile.',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: provider.fetchProfile,
                    child: const Text('Retry'),
                  ),
                ],
              ),
            );
          }

          final profile = provider.profile!;

          return ListView(
            children: [
              _sectionHeader('ACCOUNT'),
              ListTile(
                leading: const Icon(Icons.email_outlined),
                title: const Text('Email'),
                subtitle: Text(profile.email),
              ),
              _sectionHeader('PREFERENCES'),
              SwitchListTile(
                secondary: const Icon(Icons.notifications_outlined),
                title: const Text('Push notifications'),
                subtitle: const Text(
                  'Receive alerts when reminders are due',
                ),
                value: profile.notificationsEnabled,
                onChanged: provider.isSaving
                    ? null
                    : (value) async {
                        final ok =
                            await provider.setNotificationsEnabled(value);
                        if (!mounted) return;
                        if (!ok) {
                          _showError('Could not update notification setting.');
                        }
                      },
              ),
              // --- Timezone (hidden — Option A uses device local time) ---
              // ListTile(
              //   leading: const Icon(Icons.schedule_outlined),
              //   title: const Text('Timezone'),
              //   subtitle: Text(profile.timezone),
              //   trailing: provider.isSaving
              //       ? const SizedBox(
              //           width: 20,
              //           height: 20,
              //           child: CircularProgressIndicator(strokeWidth: 2),
              //         )
              //       : const Icon(Icons.chevron_right),
              //   onTap: provider.isSaving ? null : () => _pickTimezone(provider),
              // ),
              // Padding(
              //   padding: const EdgeInsets.symmetric(horizontal: 16),
              //   child: OutlinedButton.icon(
              //     onPressed: provider.isSaving
              //         ? null
              //         : () async {
              //             final ok = await provider.useDeviceTimezone();
              //             if (!mounted) return;
              //             if (!ok) {
              //               _showError('Could not set device timezone.');
              //             }
              //           },
              //     icon: const Icon(Icons.my_location_outlined),
              //     label: const Text('Use device timezone'),
              //   ),
              // ),
              _sectionHeader('SUPPORT'),
              ListTile(
                leading: const Icon(Icons.rate_review_outlined),
                title: const Text('Send feedback'),
                subtitle: const Text('Help us improve the app'),
                trailing: _isSubmittingFeedback
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.chevron_right),
                onTap: _isSubmittingFeedback ? null : _showFeedbackForm,
              ),
              ListTile(
                leading: const Icon(Icons.mail_outline),
                title: const Text('Contact support'),
                subtitle: const Text('support@aireminder.app'),
                trailing: const Icon(Icons.open_in_new),
                onTap: _contactSupport,
              ),
              ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('App version'),
                subtitle: Text(
                  _packageInfo == null
                      ? 'Loading...'
                      : '${_packageInfo!.version} (${_packageInfo!.buildNumber})',
                ),
              ),
              const Divider(height: 32),
              ListTile(
                leading: Icon(
                  Icons.logout,
                  color: Theme.of(context).colorScheme.error,
                ),
                title: Text(
                  'Sign out',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                onTap: () => context.read<AuthProvider>().logout(),
              ),
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }
}
