/// Reads a scouting report's stored markup into paragraphs of styled text
/// runs. The backend stores three `<p>` paragraphs with `<strong>` and `<em>`
/// (ARCHITECTURE.md §5.3), but the text comes from a language model and from
/// database fields, so the client treats it as untrusted: only `p`, `strong`,
/// `em` and `br` survive, with no attributes; every other tag is dropped and
/// its text kept, except the elements whose content is code or media, which
/// vanish with it. Nothing becomes live markup, no URL is read and no link
/// exists. A small tokenizer here replaces an HTML package, so the app has
/// no HTML dependency; the one function and its run type stay together
/// because they are one rule set.
library;

/// A stretch of report text with its emphasis.
typedef ReportRun = ({String text, bool bold, bool italic});

/// The most markup read, in UTF-16 code units (about 20 KB); the rest is
/// dropped before parsing.
const int reportMarkupLimit = 20 * 1024;

/// Elements dropped with everything inside them, and the pattern that finds
/// the start of each one's closing tag.
final Map<String, RegExp> _closers = {
  for (final name in const [
    'script', 'style', 'template', 'noscript', 'title', 'head', 'iframe', //
    'object', 'svg', 'math', 'canvas', 'video', 'audio', 'frameset',
  ])
    name: RegExp('</$name[\\s>/]', caseSensitive: false),
};

final RegExp _whitespace = RegExp(r'\s+');
final RegExp _tag = RegExp(r'^<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9]*)');
final RegExp _entity = RegExp(r'&(#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);');

/// Control (Cc) and format (Cf) characters, line breaks apart: bidi
/// overrides, zero-width marks, soft hyphens and the like never reach the
/// screen, whether written raw or as an entity.
final RegExp _invisible = RegExp(
  r'[\u0000-\u0009\u000B-\u001F\u007F-\u009F\u00AD\u200B-\u200F'
  r'\u202A-\u202E\u2060-\u2064\u2066-\u206F\uFEFF\uFFF9-\uFFFB]'
  r'|\u{E0001}|[\u{E0020}-\u{E007F}]',
  unicode: true,
);

const Map<String, String> _named = {
  'amp': '&',
  'lt': '<',
  'gt': '>',
  'quot': '"',
  'apos': "'",
  'nbsp': '\u00A0',
};

/// The paragraphs of [source], each a list of runs; empty paragraphs are
/// skipped. Text outside any `<p>` forms paragraphs of its own.
///
/// One linear pass: a dropped element that never closes (an unclosed or
/// truncated `<script>`) swallows the rest of the input instead of leaking
/// its body as text. A tag ends at the first `>`, so a quoted attribute
/// containing `>` ends it early and the rest of the attribute shows as text;
/// the backend never writes attributes, so this only affects hostile input,
/// and the text it exposes is still plain text.
List<List<ReportRun>> parseReportMarkup(String source) {
  final text = _capped(source);
  final lastClose = text.lastIndexOf('>');
  final paragraphs = <List<ReportRun>>[];
  var runs = <ReportRun>[];
  var bold = 0;
  var italic = 0;

  void flush() {
    if (runs.isNotEmpty) {
      runs[0] = _withText(runs.first, runs.first.text.trimLeft());
      final end = runs.length - 1;
      runs[end] = _withText(runs[end], runs[end].text.trimRight());
      final kept = [
        for (final run in runs)
          if (run.text.isNotEmpty) run,
      ];
      if (kept.isNotEmpty) paragraphs.add(kept);
    }
    runs = <ReportRun>[];
  }

  void addText(String raw) => runs.add((
    text: _unescape(raw.replaceAll(_whitespace, ' '))
        .replaceAll(_invisible, ''),
    bold: bold > 0,
    italic: italic > 0,
  ));

  var i = 0;
  while (i < text.length) {
    final open = text.indexOf('<', i);
    if (open < 0) {
      addText(text.substring(i));
      break;
    }
    if (open > i) addText(text.substring(i, open));
    i = open;
    if (text.startsWith('<!--', i)) {
      final end = text.indexOf('-->', i + 4);
      i = end < 0 ? text.length : end + 3;
      continue;
    }
    // Past the last `>` nothing can close a tag: the `<` is plain text.
    if (i > lastClose) {
      addText('<');
      i++;
      continue;
    }
    final close = text.indexOf('>', i);
    final token = text.substring(i, close + 1);
    i = close + 1;
    final tag = _tag.firstMatch(token);
    if (tag == null) continue;
    final closing = tag[1] == '/';
    final name = tag[2]!.toLowerCase();
    if (!closing && !token.endsWith('/>') && _closers.containsKey(name)) {
      final found = _closers[name]!.allMatches(text, i).firstOrNull;
      final end = found == null ? -1 : text.indexOf('>', found.start);
      i = end < 0 ? text.length : end + 1;
      continue;
    }
    switch (name) {
      case 'p':
        flush();
      case 'br':
        runs.add((text: '\n', bold: bold > 0, italic: italic > 0));
      case 'strong':
        bold = closing ? (bold > 0 ? bold - 1 : 0) : bold + 1;
      case 'em':
        italic = closing ? (italic > 0 ? italic - 1 : 0) : italic + 1;
    }
  }
  flush();
  return paragraphs;
}

ReportRun _withText(ReportRun run, String text) =>
    (text: text, bold: run.bold, italic: run.italic);

String _unescape(String text) => text.replaceAllMapped(_entity, (match) {
  final name = match[1]!;
  if (name.startsWith('#')) {
    final hex = name.startsWith('#x') || name.startsWith('#X');
    final code = int.tryParse(
      name.substring(hex ? 2 : 1),
      radix: hex ? 16 : 10,
    );
    final valid =
        code != null &&
        code > 0 &&
        code <= 0x10FFFF &&
        !(code >= 0xD800 && code <= 0xDFFF);
    return valid ? String.fromCharCode(code) : match[0]!;
  }
  return _named[name] ?? match[0]!;
});

/// [source] cut at [reportMarkupLimit], never inside a surrogate pair.
String _capped(String source) {
  if (source.length <= reportMarkupLimit) return source;
  final last = source.codeUnitAt(reportMarkupLimit - 1);
  final isHighSurrogate = last >= 0xD800 && last <= 0xDBFF;
  return source.substring(
    0,
    isHighSurrogate ? reportMarkupLimit - 1 : reportMarkupLimit,
  );
}
