/// One bulleted capability line of the capabilities pop-up.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';

/// A bold title followed by its description.
class ChatCapabilityRow extends StatelessWidget {
  const ChatCapabilityRow({
    super.key,
    required this.title,
    required this.description,
  });

  final String title;
  final String description;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 10,
      children: [
        Container(
          margin: const EdgeInsets.only(top: 6),
          width: 6,
          height: 6,
          decoration: const BoxDecoration(
            color: DelphosColors.ink,
            shape: BoxShape.circle,
          ),
        ),
        Expanded(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: '$title: ',
                  style: DelphosText.ui(weight: FontWeight.w600),
                ),
                TextSpan(
                  text: description,
                  style: DelphosText.ui(color: DelphosColors.ink2, height: 1.4),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
