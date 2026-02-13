"""Mock AWS EC2 Instance Metadata Service (IMDSv1).

Simulates the metadata endpoint at 169.254.169.254 for SSRF exploitation labs.
Only supports IMDSv1 (no token requirement) — intentionally insecure.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 80

INSTANCE_ID = "i-0abc123def456"
LOCAL_IPV4 = "10.0.0.5"
IAM_ROLE_NAME = "vulnshop-ec2-role"

# Fake AWS credentials returned by the mock IMDS
IAM_CREDENTIALS = {
    "Code": "Success",
    "LastUpdated": "2024-01-15T12:00:00Z",
    "Type": "AWS-HMAC",
    "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "Token": "FwoGZXIvYXdzEBYaDH7example+session+token",
    "Expiration": "2099-12-31T23:59:59Z",
}

# Directory listing for /latest/meta-data/
METADATA_INDEX = "\n".join([
    "ami-id",
    "hostname",
    "iam/",
    "instance-id",
    "local-ipv4",
    "public-hostname",
    "public-ipv4",
])

ROUTES: dict[str, str | dict] = {
    "/latest/meta-data/": METADATA_INDEX,
    "/latest/meta-data/instance-id": INSTANCE_ID,
    "/latest/meta-data/local-ipv4": LOCAL_IPV4,
    "/latest/meta-data/iam/security-credentials/": IAM_ROLE_NAME,
    f"/latest/meta-data/iam/security-credentials/{IAM_ROLE_NAME}": IAM_CREDENTIALS,
}


class MetadataHandler(BaseHTTPRequestHandler):
    """Handle GET requests mimicking AWS IMDS v1 behavior."""

    def do_GET(self) -> None:
        """Route GET requests to the appropriate metadata response."""
        response_body = ROUTES.get(self.path)

        if response_body is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        self.send_response(200)

        if isinstance(response_body, dict):
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_body).encode())
        else:
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(response_body.encode())

    def log_message(self, format: str, *args: object) -> None:
        """Log requests to stdout for debugging SSRF exploitation."""
        print(f"[IMDS] {self.address_string()} - {format % args}")


def run_server() -> None:
    """Start the mock IMDS HTTP server on port 80."""
    server = HTTPServer(("0.0.0.0", PORT), MetadataHandler)
    print(f"Mock IMDS running on 0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
