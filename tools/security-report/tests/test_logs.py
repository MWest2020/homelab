from secreport import logs
from secreport.layer2 import _offsite


def test_combined_plesk():
    ln = ('52.167.144.189 - - [25/Nov/2026:04:02:16 +0100] "GET /nl/plannen/index.html HTTP/1.1" 200 5448 "-" '
          '"Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"')
    r = logs.parse_line("plesk", ln)
    assert r["ts"].startswith("2026-11-25T03:02:16") and r["status"] == 200 and r["ip"] == "52.167.144.189"
    assert logs.classify_ua(r["ua"]) == ("zoekmachine", "bingbot")


def test_combined_xff_wins():
    ln = ('[pod/convergence-x/web] 2026-11-25T14:44:57.1Z 10.200.4.234 - - [25/Nov/2026:14:44:57 +0000] '
          '"GET /.env HTTP/1.1" 404 10 "-" "zgrab/0.x" "198.51.100.4"')
    r = logs.parse_line("combined", ln)
    assert r["ip"] == "198.51.100.4" and logs.SCANNER_PATHS.search(r["path"])


def test_oauth2proxy():
    ln = ('[pod/wordsworth-auth-1/oauth2-proxy] 2026-11-25T14:43:21.0Z 10.200.5.134:56646 - 5327 - mark@westerweel.work '
          '[2026/11/25 14:43:21] wordsworth.westerweel.work GET http://wordsworth-api:8000 "/documents" HTTP/1.1 '
          '"Mozilla/5.0" 200 2 0.000')
    r = logs.parse_line("oauth2proxy", ln)
    assert r["user"] == "mark@westerweel.work" and r["path"] == "/documents" and r["status"] == 200


def test_keycloak_event():
    ln = ('[pod/keycloak-1/keycloak] 2026-11-25T14:49:59.2Z 2026-11-25 14:49:59,217 WARN  [org.keycloak.events] '
          '(executor-thread-19) type="LOGIN_ERROR", realmId="7d", realmName="westerweel", clientId="admin-cli", '
          'userId="null", ipAddress="198.51.100.9", error="user_not_found", auth_method="openid-connect", username="bob"')
    r = logs.parse_line("keycloak", ln)
    assert (r["realm"], r["error"], r["username"], r["ip"]) == ("westerweel", "user_not_found", "bob", "198.51.100.9")


def test_ai_crawler():
    assert logs.classify_ua("Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)")[0] == "AI-crawler"
    assert logs.classify_ua("GitHub-Hookshot/abc")[0] == "webhook/monitor"


def test_offsite():
    assert _offsite("//evil.example/") and _offsite("/\\evil.example/") and _offsite("/\t/evil.example")
    assert not _offsite("/%2F%2Fevil.example/") and not _offsite("/")
