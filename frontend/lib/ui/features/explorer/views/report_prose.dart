/// The scouting report's text (ADR-028, DESIGN.md §3): the backend's HTML,
/// reduced by `sanitizeReportHtml` to `p`, `strong`, `em` and `br`, then
/// built into Flutter text by `HtmlWidget`. Nothing becomes live DOM, no
/// URL is fetched and no link can be followed.
///
/// Source Serif 4 at 15/1.55 in ink-2, `strong` in ink, at most 68
/// characters to the line.
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_widget_from_html_core/flutter_widget_from_html_core.dart';

import '../../../core/html/report_html_sanitizer.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';

/// Renders one report's HTML as prose.
class ReportProse extends StatelessWidget {
  const ReportProse({super.key, required this.html});

  /// The report as the backend stored it; sanitized here before rendering.
  final String html;

  /// The maximum measure, in characters (the CSS `ch` unit).
  static const int measure = 68;

  static String _css(Color color) =>
      '#${(color.toARGB32() & 0xFFFFFF).toRadixString(16).padLeft(6, '0')}';

  @override
  Widget build(BuildContext context) {
    final style = DelphosText.prose(color: DelphosColors.ink2);
    final zero = TextPainter(
      text: TextSpan(text: '0', style: style),
      textDirection: TextDirection.ltr,
      textScaler: MediaQuery.textScalerOf(context),
    )..layout();
    final maxWidth = zero.width * measure;
    zero.dispose();
    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: HtmlWidget(
        sanitizeReportHtml(html),
        textStyle: style,
        buildAsync: false,
        customStylesBuilder: (element) => switch (element.localName) {
          'strong' => {'color': _css(DelphosColors.ink)},
          'p' => {'margin': '0 0 10px 0'},
          _ => null,
        },
        // The sanitizer leaves no links; this keeps any tap a no-op.
        onTapUrl: (_) => true,
      ),
    );
  }
}
