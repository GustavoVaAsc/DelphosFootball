/// Entry point of the DelphosFootball web app: path URLs (no `#`), the
/// semantics tree on from the start, one API client for the build-time
/// backend URL, and the root widget.
library;

import 'package:flutter/semantics.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_web_plugins/url_strategy.dart';

import 'app.dart';
import 'config/api_config.dart';
import 'data/services/api_client.dart';

void main() {
  usePathUrlStrategy();
  WidgetsFlutterBinding.ensureInitialized();
  // Flutter web builds the accessibility tree only on request, behind a
  // hidden "Enable accessibility" button. Requesting it here gives screen
  // readers, keyboard focus traversal and browser tests the real tree from
  // the first frame. The handle is held for the page's lifetime.
  SemanticsBinding.instance.ensureSemantics();
  // main owns the client. It lives as long as the page; the browser drops
  // its connections on unload, so nothing closes it explicitly.
  final apiClient = ApiClient(baseUrl: ApiConfig.baseUrl);
  runApp(DelphosApp(apiClient: apiClient));
}
