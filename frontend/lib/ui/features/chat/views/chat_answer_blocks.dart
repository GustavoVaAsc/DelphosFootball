/// Block and inline Markdown parser for PitIA answers (headings, bullets,
/// numbered lists, paragraphs, bold and italic runs). Kept together in one
/// small module because its AST types and two parsers form one tiny unit.
library;

/// Kind of block inside an assistant answer.
enum ChatBlockKind { heading, bullet, numbered, paragraph }

/// A parsed block ready for layout inside `ChatAnswer`.
final class ChatAnswerBlock {
  const ChatAnswerBlock(this.kind, this.text, {this.marker});

  final ChatBlockKind kind;
  final String text;
  final String? marker;
}

/// An inline text run with optional bold or italic styling.
final class ChatInlineRun {
  const ChatInlineRun(this.text, {this.bold = false, this.italic = false});

  final String text;
  final bool bold;
  final bool italic;
}

final RegExp _headingRe = RegExp(r'^#{1,3}\s+(.+)$');
final RegExp _bulletRe = RegExp(r'^\s*[-*•]\s+(.+)$');
final RegExp _numberedRe = RegExp(r'^\s*(\d+[.)])\s+(.+)$');
final RegExp _wrappedBoldRe = RegExp(r'^\*\*([^*]+)\*\*$');

/// Splits [raw] into headings, bullets, numbered items and paragraphs.
List<ChatAnswerBlock> parseChatAnswerBlocks(String raw) {
  final blocks = <ChatAnswerBlock>[];
  final paragraph = <String>[];

  void flushParagraph() {
    if (paragraph.isEmpty) return;
    blocks.add(ChatAnswerBlock(ChatBlockKind.paragraph, paragraph.join('\n')));
    paragraph.clear();
  }

  for (final line in raw.split(RegExp(r'\r?\n'))) {
    final trimmed = line.trim();
    if (trimmed.isEmpty) {
      flushParagraph();
      continue;
    }
    if (_headingRe.firstMatch(trimmed) case final m?) {
      flushParagraph();
      var title = m.group(1)!.trim();
      if (_wrappedBoldRe.firstMatch(title) case final inner?) {
        title = inner.group(1)!.trim();
      }
      blocks.add(ChatAnswerBlock(ChatBlockKind.heading, title));
    } else if (_bulletRe.firstMatch(line) case final m?) {
      flushParagraph();
      blocks.add(ChatAnswerBlock(ChatBlockKind.bullet, m.group(1)!.trim()));
    } else if (_numberedRe.firstMatch(line) case final m?) {
      flushParagraph();
      blocks.add(
        ChatAnswerBlock(
          ChatBlockKind.numbered,
          m.group(2)!.trim(),
          marker: m.group(1)!,
        ),
      );
    } else {
      paragraph.add(trimmed);
    }
  }
  flushParagraph();
  return blocks;
}

/// Splits [text] into plain, `**bold**` and `*italic*` runs without choking on
/// unclosed markers.
List<ChatInlineRun> parseChatInlineRuns(String text) {
  final runs = <ChatInlineRun>[];
  var cursor = 0;
  while (cursor < text.length) {
    final boldStart = text.indexOf('**', cursor);
    final boldClose = boldStart >= 0 ? text.indexOf('**', boldStart + 2) : -1;
    if (boldStart >= 0 && boldClose > boldStart + 2) {
      if (boldStart > cursor) {
        _appendItalicRuns(text.substring(cursor, boldStart), runs);
      }
      runs.add(
        ChatInlineRun(text.substring(boldStart + 2, boldClose), bold: true),
      );
      cursor = boldClose + 2;
      continue;
    }
    _appendItalicRuns(text.substring(cursor), runs);
    break;
  }
  return runs;
}

void _emitPlain(String text, List<ChatInlineRun> out) {
  if (text.isEmpty) return;
  if (out.isNotEmpty && !out.last.bold && !out.last.italic) {
    out[out.length - 1] = ChatInlineRun(out.last.text + text);
    return;
  }
  out.add(ChatInlineRun(text));
}

void _appendItalicRuns(String segment, List<ChatInlineRun> out) {
  var cursor = 0;
  while (cursor < segment.length) {
    final start = segment.indexOf('*', cursor);
    if (start < 0 || start + 1 >= segment.length) {
      _emitPlain(segment.substring(cursor), out);
      return;
    }
    if (segment[start + 1] == '*') {
      _emitPlain(segment.substring(cursor, start + 2), out);
      cursor = start + 2;
      continue;
    }
    if (segment[start + 1] == ' ') {
      _emitPlain(segment.substring(cursor, start + 1), out);
      cursor = start + 1;
      continue;
    }
    var close = segment.indexOf('*', start + 1);
    while (close >= 0 &&
        (close == start + 1 ||
            segment[close - 1] == ' ' ||
            (close + 1 < segment.length && segment[close + 1] == '*'))) {
      close = segment.indexOf('*', close + 1);
    }
    if (close < 0) {
      _emitPlain(segment.substring(cursor), out);
      return;
    }
    _emitPlain(segment.substring(cursor, start), out);
    out.add(ChatInlineRun(segment.substring(start + 1, close), italic: true));
    cursor = close + 1;
  }
}
