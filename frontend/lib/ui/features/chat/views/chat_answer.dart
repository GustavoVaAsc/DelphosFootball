/// The assistant's answer in Source Sans 3, formatted into structured blocks
/// (paragraphs, headings, bullets and numbered lists) and capped at 96 chars.
library;

import 'package:material_ui/material_ui.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import 'chat_answer_blocks.dart';

/// Sans-serif answer prose in ink-2 with structured list/heading blocks.
class ChatAnswer extends StatelessWidget {
  const ChatAnswer({super.key, required this.text});

  final String text;

  /// The maximum measure, in characters (DESIGN.md §3).
  static const int measure = 96;

  /// Base answer style using Source Sans 3 at body size (14 px).
  static TextStyle bodyStyle({
    FontWeight weight = FontWeight.w400,
    Color color = DelphosColors.ink2,
    bool tabular = false,
  }) => DelphosText.ui(
    size: TypeScale.body,
    weight: weight,
    color: color,
    height: 1.55,
    tabular: tabular,
  );

  @override
  Widget build(BuildContext context) {
    final style = bodyStyle();
    final zero = TextPainter(
      text: TextSpan(text: '0', style: style),
      textDirection: TextDirection.ltr,
      textScaler: MediaQuery.textScalerOf(context),
    )..layout();
    final maxWidth = zero.width * measure;
    zero.dispose();

    final blocks = parseChatAnswerBlocks(text);
    if (blocks.length <= 1 &&
        (blocks.isEmpty || blocks.first.kind == ChatBlockKind.paragraph)) {
      return ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: _richText(
          blocks.isEmpty ? text : blocks.first.text,
          base: style,
        ),
      );
    }

    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 8,
        children: [
          for (final (i, block) in blocks.indexed)
            _blockWidget(block, base: style, isFirst: i == 0),
        ],
      ),
    );
  }

  Widget _blockWidget(
    ChatAnswerBlock block, {
    required TextStyle base,
    required bool isFirst,
  }) => switch (block.kind) {
    ChatBlockKind.heading => Padding(
      padding: EdgeInsets.only(top: isFirst ? 0 : 4),
      child: _richText(
        block.text,
        base: bodyStyle(weight: FontWeight.w700, color: DelphosColors.ink),
      ),
    ),
    ChatBlockKind.bullet => Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 8,
      children: [
        Text(
          '•',
          style: bodyStyle(weight: FontWeight.w700, color: DelphosColors.ink3),
        ),
        Expanded(child: _richText(block.text, base: base)),
      ],
    ),
    ChatBlockKind.numbered => Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 6,
      children: [
        Text(
          block.marker!,
          style: bodyStyle(
            weight: FontWeight.w600,
            color: DelphosColors.ink3,
            tabular: true,
          ),
        ),
        Expanded(child: _richText(block.text, base: base)),
      ],
    ),
    ChatBlockKind.paragraph => _richText(block.text, base: base),
  };

  Widget _richText(String source, {required TextStyle base}) {
    final emphasis = bodyStyle(
      weight: FontWeight.w600,
      color: DelphosColors.ink,
    );
    final runs = parseChatInlineRuns(source);
    return SelectableText.rich(
      TextSpan(
        style: base,
        children: [
          for (final run in runs)
            TextSpan(
              text: run.text,
              style: run.bold
                  ? emphasis
                  : (run.italic
                        ? base.copyWith(fontStyle: FontStyle.italic)
                        : null),
            ),
        ],
      ),
    );
  }
}
