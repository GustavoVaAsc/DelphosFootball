/// A 1 px `--rule` divider between the sections of a turn.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';

/// Separates the parts of a turn without a border or ground of their own.
class ChatHairline extends StatelessWidget {
  const ChatHairline({super.key});

  @override
  Widget build(BuildContext context) =>
      const SizedBox(height: 1, child: ColoredBox(color: DelphosColors.rule));
}
