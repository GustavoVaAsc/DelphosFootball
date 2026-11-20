/// The scouting report's text (DESIGN.md §3): the stored markup read by
/// `parseReportMarkup`, which keeps only paragraphs, bold and italic, then
/// drawn as Flutter text. Nothing becomes live markup, no URL is fetched and
/// no link can be followed.
///
/// Source Serif 4 at 15/1.55 in ink-2, bold runs in ink, at most 68
/// characters to the line.
library;

import 'package:flutter/widgets.dart';

import '../../../core/html/report_markup.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';

/// Renders one report's markup as prose.
class ReportProse extends StatelessWidget {
  const ReportProse({super.key, required this.html});

  /// The report as the backend stored it; read here, never rendered raw.
  final String html;

  /// The maximum measure, in characters (the CSS `ch` unit).
  static const int measure = 68;

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
    final emphasis = DelphosText.prose(
      weight: FontWeight.w600,
      color: DelphosColors.ink,
    );
    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: 10,
        children: [
          for (final paragraph in parseReportMarkup(html))
            Text.rich(
              TextSpan(
                style: style,
                children: [
                  for (final run in paragraph)
                    TextSpan(
                      text: run.text,
                      style: run.bold
                          ? emphasis.copyWith(
                              fontStyle: run.italic ? FontStyle.italic : null,
                            )
                          : (run.italic
                                ? style.copyWith(fontStyle: FontStyle.italic)
                                : null),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
