import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../data/data.dart';
import '../../design/theme.dart';
import '../../design/tokens.dart';
import '../../design/typography.dart';
import '../../design/widgets/app_buttons.dart';
import '../../design/widgets/app_scaffold.dart';
import '../../design/widgets/feedback.dart';
import '../../l10n/app_localizations.dart';

/// The market's own brochure page, shown inside the app (A101, CarrefourSA,
/// Gratis, or any market's site from its empty state).
///
/// "Geri" in the top bar always returns to the app. Moving back inside the
/// web site has its own button at the bottom, shown only when there is
/// somewhere to go back to.
class WebCatalogScreen extends ConsumerStatefulWidget {
  const WebCatalogScreen({super.key, required this.chainId});

  final String chainId;

  @override
  ConsumerState<WebCatalogScreen> createState() => _WebCatalogScreenState();
}

class _WebCatalogScreenState extends ConsumerState<WebCatalogScreen> {
  WebViewController? _controller;
  String? _loadedUrl;

  /// 0–100 while a page loads, null when idle.
  int? _progress = 0;
  bool _everFinished = false;
  bool _failed = false;
  bool _canGoBack = false;

  void _start(String url) {
    _loadedUrl = url;
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (progress) {
            if (mounted) setState(() => _progress = progress);
          },
          onPageStarted: (_) {
            if (mounted) setState(() => _progress = 0);
          },
          onPageFinished: (_) => _onFinished(),
          onUrlChange: (_) async {
            final canGoBack = await _controller?.canGoBack() ?? false;
            if (mounted && canGoBack != _canGoBack) {
              setState(() => _canGoBack = canGoBack);
            }
          },
          onWebResourceError: (error) {
            // Only a failure of the page itself counts; a missing advert or
            // tracker does not.
            if ((error.isForMainFrame ?? false) && mounted) {
              setState(() {
                _failed = true;
                _progress = null;
              });
            }
          },
          onNavigationRequest: (request) {
            final scheme = Uri.tryParse(request.url)?.scheme ?? '';
            // Stay on the web: no jumps into other apps or app stores.
            return scheme == 'https' || scheme == 'http' || scheme == 'about'
                ? NavigationDecision.navigate
                : NavigationDecision.prevent;
          },
        ),
      );
    _controller = controller;
    controller.loadRequest(Uri.parse(url));
  }

  Future<void> _onFinished() async {
    final canGoBack = await _controller?.canGoBack() ?? false;
    if (!mounted) return;
    setState(() {
      _progress = null;
      _everFinished = true;
      _canGoBack = canGoBack;
    });
  }

  void _retry() {
    setState(() {
      _failed = false;
      _progress = 0;
    });
    final url = _loadedUrl;
    if (_everFinished) {
      _controller?.reload();
    } else if (url != null) {
      _controller?.loadRequest(Uri.parse(url));
    }
  }

  Future<void> _goBackInSite() async {
    final controller = _controller;
    if (controller == null) return;
    if (await controller.canGoBack()) {
      await controller.goBack();
    }
  }

  Future<void> _openInBrowser(String url) async {
    final l10n = AppLocalizations.of(context);
    var opened = false;
    try {
      opened = await launchUrl(
        Uri.parse(url),
        mode: LaunchMode.externalApplication,
      );
    } on Object {
      opened = false;
    }
    if (!opened && mounted) showAppMessage(context, l10n.browserFailed);
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final chain = ref.watch(chainProvider(widget.chainId)).value;

    if (chain == null) {
      return AppScaffold(
        topBar: const AppTopBar(),
        body: StateView(
          icon: Icons.storefront_rounded,
          title: l10n.unknownChainTitle,
        ),
      );
    }
    if (_controller == null) _start(chain.webUrl);
    final controller = _controller!;
    final progress = _progress;

    return PopScope(
      // The phone's own back key steps back inside the site first.
      canPop: !_canGoBack || _failed,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _goBackInSite();
      },
      child: AppScaffold(
        topBar: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppTopBar(
              title: chain.name,
              subtitle: l10n.cardWeb,
              keepOnOneRow: true,
              onBack: () => Navigator.of(context).pop(),
            ),
            SizedBox(
              height: AppSpace.xxs,
              child: progress == null || _failed
                  ? null
                  : LinearProgressIndicator(
                      value: progress <= 0 ? null : progress / 100,
                      minHeight: AppSpace.xxs,
                    ),
            ),
          ],
        ),
        body: _failed
            ? WebCatalogError(
                chainName: chain.name,
                onRetry: _retry,
                onOpenInBrowser: () => _openInBrowser(chain.webUrl),
              )
            : Stack(
                fit: StackFit.expand,
                children: [
                  WebViewWidget(controller: controller),
                  if (!_everFinished)
                    ColoredBox(
                      color: c.paper,
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.all(AppSpace.xl),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const SizedBox.square(
                                dimension: AppSize.touch,
                                child: CircularProgressIndicator(
                                  strokeWidth: AppSpace.xxs,
                                ),
                              ),
                              const SizedBox(height: AppSpace.md),
                              Text(
                                l10n.webLoading,
                                textAlign: TextAlign.center,
                                style: AppType.body.copyWith(color: c.inkSoft),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                ],
              ),
        bottomBar: _failed
            ? null
            : WebCatalogBar(
                canGoBack: _canGoBack,
                onBackInSite: _goBackInSite,
                onOpenInBrowser: () => _openInBrowser(chain.webUrl),
              ),
      ),
    );
  }
}

/// Bottom bar of the web view: "Sitede geri" (only when possible) and
/// "Tarayıcıda aç".
class WebCatalogBar extends StatelessWidget {
  const WebCatalogBar({
    super.key,
    required this.canGoBack,
    required this.onBackInSite,
    required this.onOpenInBrowser,
  });

  final bool canGoBack;
  final VoidCallback onBackInSite;
  final VoidCallback onOpenInBrowser;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final l10n = AppLocalizations.of(context);
    final back = AppButton(
      label: l10n.webBack,
      icon: Icons.undo_rounded,
      kind: AppButtonKind.tonal,
      minHeight: AppSize.touch,
      expand: true,
      onPressed: canGoBack ? onBackInSite : null,
    );
    final browser = AppButton(
      label: l10n.openInBrowser,
      icon: Icons.open_in_new_rounded,
      kind: AppButtonKind.outline,
      minHeight: AppSize.touch,
      expand: true,
      onPressed: onOpenInBrowser,
    );
    return DecoratedBox(
      decoration: BoxDecoration(
        color: c.paper,
        border: Border(
          top: BorderSide(color: c.line, width: AppSize.hairline),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.sm),
        child: context.useStackedBars
            ? Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (canGoBack) ...[back, const SizedBox(height: AppSpace.xs)],
                  browser,
                ],
              )
            : Row(
                children: [
                  if (canGoBack) ...[
                    Expanded(child: back),
                    const SizedBox(width: AppSpace.xs),
                  ],
                  Expanded(child: browser),
                ],
              ),
      ),
    );
  }
}

/// Shown when the market's page cannot be opened.
class WebCatalogError extends StatelessWidget {
  const WebCatalogError({
    super.key,
    required this.chainName,
    required this.onRetry,
    required this.onOpenInBrowser,
  });

  final String chainName;
  final VoidCallback onRetry;
  final VoidCallback onOpenInBrowser;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return StateView(
      icon: Icons.wifi_off_rounded,
      title: l10n.webErrorTitle,
      message: l10n.webErrorMessage(chainName),
      actionLabel: l10n.retry,
      actionIcon: Icons.refresh_rounded,
      onAction: onRetry,
      secondaryLabel: l10n.openInBrowser,
      secondaryIcon: Icons.open_in_new_rounded,
      onSecondary: onOpenInBrowser,
    );
  }
}
