/// The allowlist sanitizer for report HTML (ADR-028), applied before the
/// report reaches `HtmlWidget`, so the widget only ever sees `p`, `strong`,
/// `em` and `br` with no attributes and escaped text.
///
/// The backend already escapes the report, but the text comes from a
/// language model and from database fields, so the client treats it as
/// untrusted. Parsing uses `package:html`, the parser `HtmlWidget` uses
/// itself; this module only decides what survives.
library;

import 'dart:convert';

import 'package:html/dom.dart' as dom;
import 'package:html/parser.dart' as html;

/// The most report HTML read, in UTF-16 code units (about 20 KB); the rest
/// is dropped before parsing.
const int reportHtmlLimit = 20 * 1024;

const Set<String> _kept = {'p', 'strong', 'em'};

/// Elements dropped with everything inside them: their content is code,
/// a URL fetch, or media, never report prose.
const Set<String> _dropped = {
  'script', 'style', 'template', 'noscript', 'title', 'head', //
  'img', 'picture', 'source', 'track', 'video', 'audio', 'canvas',
  'iframe', 'frame', 'frameset', 'object', 'embed', 'svg', 'math',
};

const HtmlEscape _escape = HtmlEscape(HtmlEscapeMode.element);

/// [source] reduced to `p`, `strong`, `em` and `br` without attributes.
/// Any other element is unwrapped to its text, the elements in `_dropped`
/// disappear with their content, and comments are removed.
String sanitizeReportHtml(String source) {
  final out = StringBuffer();
  void walk(dom.Node parent) {
    for (final node in parent.nodes) {
      switch (node) {
        case dom.Text(:final data):
          out.write(_escape.convert(data));
        case dom.Element(:final localName?) when _dropped.contains(localName):
          break;
        case dom.Element(localName: 'br'):
          out.write('<br>');
        case dom.Element(:final localName?) when _kept.contains(localName):
          out.write('<$localName>');
          walk(node);
          out.write('</$localName>');
        case dom.Element():
          walk(node);
        default:
          break;
      }
    }
  }

  walk(html.parseFragment(_capped(source)));
  return out.toString();
}

/// [source] cut at [reportHtmlLimit], never inside a surrogate pair.
String _capped(String source) {
  if (source.length <= reportHtmlLimit) return source;
  final last = source.codeUnitAt(reportHtmlLimit - 1);
  final isHighSurrogate = last >= 0xD800 && last <= 0xDBFF;
  return source.substring(
    0,
    isHighSurrogate ? reportHtmlLimit - 1 : reportHtmlLimit,
  );
}
