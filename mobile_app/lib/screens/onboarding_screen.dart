import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../services/onboarding_permissions.dart';
import '../services/onboarding_storage.dart';
import '../widgets/onboarding/animated_gradient_background.dart';
import '../widgets/onboarding/onboarding_illustrations.dart';

class OnboardingScreen extends StatefulWidget {
  final VoidCallback onFinished;

  const OnboardingScreen({
    super.key,
    required this.onFinished,
  });

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _pageIndex = 0;
  bool _busy = false;

  static const _pages = <_OnboardingPageData>[
    _OnboardingPageData(
      kind: OnboardingIllustrationKind.welcome,
      title: 'Never miss what matters',
      body:
          'AI Reminder helps you remember the right thing at the right time — without fiddling with forms.',
      isPermissionPage: false,
    ),
    _OnboardingPageData(
      kind: OnboardingIllustrationKind.chat,
      title: 'Just say it naturally',
      body:
          'Type or speak like you would to a friend: "Remind me to take medicine at 9 PM." We handle the rest.',
      isPermissionPage: false,
    ),
    _OnboardingPageData(
      kind: OnboardingIllustrationKind.notifications,
      title: 'Stay on time',
      body:
          'Allow notifications so we can nudge you when a reminder is due. You can change this anytime in Profile.',
      isPermissionPage: true,
      permissionType: _PermissionType.notifications,
    ),
    _OnboardingPageData(
      kind: OnboardingIllustrationKind.voice,
      title: 'Hands-free reminders',
      body:
          'Enable the microphone to create reminders by voice in Chat. Optional — you can skip and enable later.',
      isPermissionPage: true,
      permissionType: _PermissionType.microphone,
    ),
  ];

  int get _lastIndex => _pages.length - 1;

  Future<void> _finish() async {
    await OnboardingStorage.markComplete();
    widget.onFinished();
  }

  void _nextPage() {
    if (_pageIndex >= _lastIndex) {
      _finish();
      return;
    }
    _pageController.nextPage(
      duration: const Duration(milliseconds: 480),
      curve: Curves.easeOutCubic,
    );
  }

  Future<void> _requestPermission(_PermissionType type) async {
    if (kIsWeb) {
      _nextPage();
      return;
    }

    setState(() => _busy = true);
    try {
      switch (type) {
        case _PermissionType.notifications:
          await OnboardingPermissions.requestNotifications();
        case _PermissionType.microphone:
          await OnboardingPermissions.requestMicrophone();
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        _nextPage();
      }
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final page = _pages[_pageIndex];

    return Scaffold(
      body: AnimatedGradientBackground(
        child: SafeArea(
          child: Column(
            children: [
              if (_pageIndex < _lastIndex)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: _busy ? null : _finish,
                    child: Text(
                      'Skip',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.95),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                )
              else
                const SizedBox(height: 48),
              Expanded(
                child: PageView.builder(
                  controller: _pageController,
                  itemCount: _pages.length,
                  onPageChanged: (index) => setState(() => _pageIndex = index),
                  itemBuilder: (context, index) {
                    final data = _pages[index];
                    return _OnboardingPageContent(
                      data: data,
                      visible: index == _pageIndex,
                    );
                  },
                ),
              ),
              _PageIndicator(
                count: _pages.length,
                index: _pageIndex,
              ),
              const SizedBox(height: 20),
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 28),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (page.isPermissionPage) ...[
                      FilledButton(
                        onPressed: _busy
                            ? null
                            : () => _requestPermission(page.permissionType!),
                        style: FilledButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: const Color(0xFF6750A4),
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        child: _busy
                            ? const SizedBox(
                                height: 22,
                                width: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Color(0xFF6750A4),
                                ),
                              )
                            : Text(_permissionButtonLabel(page.permissionType!)),
                      ),
                      const SizedBox(height: 10),
                      TextButton(
                        onPressed: _busy ? null : _nextPage,
                        child: Text(
                          page.permissionType == _PermissionType.microphone
                              ? 'Skip for now'
                              : 'Not now',
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.9),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ] else ...[
                      FilledButton(
                        onPressed: _nextPage,
                        style: FilledButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: const Color(0xFF6750A4),
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        child: Text(
                          _pageIndex == _lastIndex ? 'Get started' : 'Continue',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _permissionButtonLabel(_PermissionType type) {
    switch (type) {
      case _PermissionType.notifications:
        return 'Enable notifications';
      case _PermissionType.microphone:
        return 'Enable microphone';
    }
  }
}

enum _PermissionType { notifications, microphone }

class _OnboardingPageData {
  final OnboardingIllustrationKind kind;
  final String title;
  final String body;
  final bool isPermissionPage;
  final _PermissionType? permissionType;

  const _OnboardingPageData({
    required this.kind,
    required this.title,
    required this.body,
    this.isPermissionPage = false,
    this.permissionType,
  });
}

class _OnboardingPageContent extends StatefulWidget {
  final _OnboardingPageData data;
  final bool visible;

  const _OnboardingPageContent({
    required this.data,
    required this.visible,
  });

  @override
  State<_OnboardingPageContent> createState() => _OnboardingPageContentState();
}

class _OnboardingPageContentState extends State<_OnboardingPageContent>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fadeController;
  late final Animation<double> _fade;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _fade = CurvedAnimation(parent: _fadeController, curve: Curves.easeOut);
    _slide = Tween<Offset>(
      begin: const Offset(0, 0.08),
      end: Offset.zero,
    ).animate(_fade);
    if (widget.visible) {
      _fadeController.forward();
    }
  }

  @override
  void didUpdateWidget(covariant _OnboardingPageContent oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.visible && !oldWidget.visible) {
      _fadeController.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fade,
      child: SlideTransition(
        position: _slide,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              OnboardingIllustration(kind: widget.data.kind),
              const SizedBox(height: 36),
              Text(
                widget.data.title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                  height: 1.2,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                widget.data.body,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  height: 1.45,
                  color: Colors.white.withValues(alpha: 0.92),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PageIndicator extends StatelessWidget {
  final int count;
  final int index;

  const _PageIndicator({required this.count, required this.index});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(count, (i) {
        final active = i == index;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic,
          margin: const EdgeInsets.symmetric(horizontal: 4),
          height: 8,
          width: active ? 28 : 8,
          decoration: BoxDecoration(
            color: active
                ? Colors.white
                : Colors.white.withValues(alpha: 0.45),
            borderRadius: BorderRadius.circular(8),
          ),
        );
      }),
    );
  }
}
