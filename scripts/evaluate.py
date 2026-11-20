"""Run the synthetic evaluation against the local application as a signed-in manager."""

import argparse
import json
from getpass import getpass
from http.client import HTTPConnection
from http.cookies import SimpleCookie


def run(email, password, port):
    origin = f"http://localhost:{port}"
    connection = HTTPConnection("localhost", port, timeout=45)
    headers = {"Origin": origin, "Content-Type": "application/json"}
    try:
        connection.request(
            "POST",
            "/api/v1/auth/login",
            json.dumps({"email": email, "password": password}),
            headers,
        )
        response = connection.getresponse()
        response.read()
        if response.status != 200:
            raise SystemExit(f"Sign-in failed (HTTP {response.status})")
        cookies = SimpleCookie()
        for k, v in response.getheaders():
            if k.lower() == "set-cookie":
                cookies.load(v)
        headers["Cookie"] = "; ".join(m.key + "=" + m.value for m in cookies.values())
        headers["X-CSRF-Token"] = cookies["__Host-creative_csrf"].value
        try:
            connection.request("POST", "/api/v1/admin/evaluations", headers=headers)
            response = connection.getresponse()
            body = response.read()
            if response.status != 201:
                raise SystemExit(f"Evaluation failed (HTTP {response.status})")
            return json.loads(body)["data"]
        finally:
            connection.request("POST", "/api/v1/auth/logout", headers=headers)
            connection.getresponse().read()
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--port", type=int, default=3100)
    args = parser.parse_args()
    print(json.dumps(run(args.email, getpass("Agency password: "), args.port), indent=2))
