import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/auth_provider.dart';
import '../services/feedback_service.dart';
import '../services/profile_provider.dart';
import '../utils/chat_retention_options.dart';
import '../widgets/app_chrome.dart';
import 'verify_email_otp_screen.dart';
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
      barrierColor: AppChrome.ink.withValues(alpha: 0.32),
      builder: (context) {
        return Dialog(
          backgroundColor: Colors.transparent,
          insetPadding: const EdgeInsets.symmetric(horizontal: 24),
          child: GlassPanel(
            borderRadius: 28,
            color: Colors.white.withValues(alpha: 0.94),
            padding: const EdgeInsets.all(22),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          color: AppChrome.primary.withValues(alpha: 0.1),
                          border: Border.all(
                            color: AppChrome.primary.withValues(alpha: 0.18),
                          ),
                        ),
                        child: const Icon(
                          Icons.rate_review_rounded,
                          color: AppChrome.primary,
                        ),
                      ),
                      const SizedBox(width: 14),
                      const Expanded(
                        child: Text(
                          'Send feedback',
                          style: TextStyle(
                            color: AppChrome.ink,
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'Tell us what you like or what we should improve.',
                    style: TextStyle(color: AppChrome.muted, height: 1.4),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: controller,
                    maxLines: 5,
                    maxLength: 2000,
                    decoration: AppChrome.inputDecoration(
                      label: 'Feedback description',
                      hint: 'Your feedback...',
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        style: TextButton.styleFrom(
                          foregroundColor: AppChrome.muted,
                          textStyle: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        child: const Text('Cancel'),
                      ),
                      const SizedBox(width: 8),
                      FilledButton(
                        onPressed: () {
                          if (controller.text.trim().length < 3) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Please enter at least 3 characters.',
                                ),
                              ),
                            );
                            return;
                          }
                          Navigator.pop(context, true);
                        },
                        style: AppChrome.primaryButtonStyle(),
                        child: const Text('Submit'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
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

  Future<void> _pickChatRetention(ProfileProvider provider) async {
    final current = provider.chatRetentionDays;
    final selected = await showModalBottomSheet<ChatRetentionOption>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(24, 0, 24, 4),
              child: Text(
                'Keep chat history',
                style: TextStyle(
                  color: AppChrome.ink,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(24, 0, 24, 8),
              child: Text(
                'Older messages are deleted automatically.',
                style: TextStyle(color: AppChrome.muted),
              ),
            ),
            for (final option in kChatRetentionOptions)
              ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 24),
                title: Text(option.label),
                trailing: option.days == current
                    ? const Icon(Icons.check_rounded, color: AppChrome.primary)
                    : null,
                onTap: () => Navigator.of(sheetContext).pop(option),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (selected == null || selected.days == current) return;
    final ok = await provider.setChatRetentionDays(selected.days);
    if (!mounted) return;
    if (!ok) {
      _showError('Could not update chat history setting.');
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
      padding: const EdgeInsets.fromLTRB(4, 20, 4, 8),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w900,
          color: AppChrome.primary,
          letterSpacing: 1.0,
        ),
      ),
    );
  }

  Widget _buildSettingsIcon() {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: AppChrome.primary.withValues(alpha: 0.1),
        border: Border.all(color: AppChrome.primary.withValues(alpha: 0.18)),
      ),
      child: const Icon(
        Icons.settings_suggest_rounded,
        color: AppChrome.primary,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SpeakardoScaffold(
      child: Consumer<ProfileProvider>(
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
                    style: AppChrome.primaryButtonStyle(),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            );
          }

          final profile = provider.profile!;

          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 112),
            children: [
              SpeakardoTopBar(
                title: 'System Settings',
                subtitle: 'Manage your profile and preferences',
                leading: _buildSettingsIcon(),
              ),
              const SizedBox(height: 12),
              if (!profile.emailVerified) ...[
                GlassPanel(
                  borderRadius: 22,
                  color: Colors.amber.withValues(alpha: 0.08),
                  borderColor: Colors.amber.withValues(alpha: 0.25),
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: const [
                          Icon(Icons.warning_amber_rounded, color: Colors.amber),
                          SizedBox(width: 10),
                          Text(
                            'Verify your email',
                            style: TextStyle(
                              color: AppChrome.ink,
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Check your inbox for a 6-digit code, or verify below.',
                        style: TextStyle(
                          color: AppChrome.muted,
                          fontSize: 13,
                          height: 1.35,
                        ),
                      ),
                      const SizedBox(height: 12),
                      FilledButton.tonal(
                        onPressed: () {
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => const VerifyEmailOtpScreen(),
                            ),
                          );
                        },
                        child: const Text('Verify email'),
                      ),
                    ],
                  ),
                ),
              ],
              _sectionHeader('Account'),
              const SizedBox(height: 8),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                child: ListTile(
                  leading: const Icon(Icons.email_outlined, color: AppChrome.primary),
                  title: const Text(
                    'Email',
                    style: TextStyle(
                      color: AppChrome.ink,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  subtitle: Text(
                    profile.email,
                    style: const TextStyle(color: AppChrome.muted),
                  ),
                  trailing: profile.emailVerified
                      ? const Icon(
                          Icons.verified,
                          color: AppChrome.accent,
                          size: 22,
                        )
                      : const Text(
                          'Unverified',
                          style: TextStyle(
                            color: Colors.amber,
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                ),
              ),
              _sectionHeader('Preferences'),
              const SizedBox(height: 8),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    SwitchListTile.adaptive(
                      secondary: const Icon(Icons.notifications_outlined, color: AppChrome.primary),
                      title: const Text(
                        'Push notifications',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: const Text(
                        'Receive alerts when reminders are due',
                        style: TextStyle(color: AppChrome.muted),
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
                    const Divider(
                      height: 1,
                      indent: 56,
                      endIndent: 16,
                      color: AppChrome.line,
                    ),
                    ListTile(
                      leading: const Icon(Icons.history_rounded, color: AppChrome.primary),
                      title: const Text(
                        'Chat history',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: Text(
                        chatRetentionLabel(profile.chatRetentionDays),
                        style: const TextStyle(color: AppChrome.muted),
                      ),
                      trailing: const Icon(
                        Icons.chevron_right_rounded,
                        color: AppChrome.muted,
                      ),
                      onTap: provider.isSaving
                          ? null
                          : () => _pickChatRetention(provider),
                    ),
                  ],
                ),
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
              _sectionHeader('Support & Feedback'),
              const SizedBox(height: 8),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    ListTile(
                      leading: const Icon(Icons.rate_review_outlined, color: AppChrome.primary),
                      title: const Text(
                        'Send feedback',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: const Text(
                        'Help us improve the app',
                        style: TextStyle(color: AppChrome.muted),
                      ),
                      trailing: _isSubmittingFeedback
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.chevron_right_rounded, color: AppChrome.muted),
                      onTap: _isSubmittingFeedback ? null : _showFeedbackForm,
                    ),
                    const Divider(
                      height: 1,
                      indent: 56,
                      endIndent: 16,
                      color: AppChrome.line,
                    ),
                    ListTile(
                      leading: const Icon(Icons.mail_outline, color: AppChrome.primary),
                      title: const Text(
                        'Contact support',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: const Text(
                        'support@aireminder.app',
                        style: TextStyle(color: AppChrome.muted),
                      ),
                      trailing: const Icon(
                        Icons.open_in_new_rounded,
                        color: AppChrome.muted,
                        size: 20,
                      ),
                      onTap: _contactSupport,
                    ),
                    const Divider(
                      height: 1,
                      indent: 56,
                      endIndent: 16,
                      color: AppChrome.line,
                    ),
                    ListTile(
                      leading: const Icon(Icons.info_outline, color: AppChrome.primary),
                      title: const Text(
                        'App version',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: Text(
                        _packageInfo == null
                            ? 'Loading...'
                            : '${_packageInfo!.version} (${_packageInfo!.buildNumber})',
                        style: const TextStyle(color: AppChrome.muted),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                color: Colors.redAccent.withValues(alpha: 0.08),
                borderColor: Colors.redAccent.withValues(alpha: 0.22),
                child: ListTile(
                  leading: const Icon(Icons.logout_rounded, color: Colors.redAccent),
                  title: const Text(
                    'Sign out',
                    style: TextStyle(
                      color: Colors.redAccent,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  onTap: () => context.read<AuthProvider>().logout(),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
