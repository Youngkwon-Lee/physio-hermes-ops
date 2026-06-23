#!/usr/bin/env python3
import argparse
import json
import sys

import hometax_codef_client as client


def build_payload(args):
    status = client.credentials_status()
    payload = {
        "provider": "codef",
        "configured": status["configured"],
        "sandbox": status["sandbox"],
        "available_doc_types": status["available_doc_types"],
        "credential_sources": status["credential_sources"],
        "mode": "config-only" if args.check_config_only else "dry-run",
    }
    if not args.check_config_only:
        sample_identity = args.identity_sample or "1234567890"
        payload["request_preview"] = client.fetch_hometax(
            doc_type=args.doc_type,
            identity=sample_identity,
            user_name=args.user_name,
            year=args.year,
            dry_run=True,
        )
    return payload


def print_text(payload):
    print("[홈택스 MVP 상태]")
    print(
        f"provider={payload['provider']} sandbox={1 if payload['sandbox'] else 0} "
        f"configured={'yes' if payload['configured'] else 'no'}"
    )
    print("지원 문서: " + ", ".join(payload["available_doc_types"]))
    print("실행 모드: " + payload["mode"])
    if "request_preview" in payload:
        preview = payload["request_preview"]
        print(
            f"미리보기: stage={preview.get('stage')} "
            f"doc_type={preview.get('doc_type')} identity={preview.get('masked_identity')}"
        )


def main() -> int:
    p = argparse.ArgumentParser(description="홈택스 MVP/CODEF 상태 요약")
    p.add_argument("--doc-type", default="biz_reg_proof", choices=list(client.DOC_PATHS.keys()))
    p.add_argument("--year", default=None)
    p.add_argument("--user-name", default="홍길동")
    p.add_argument("--identity-sample", default="1234567890")
    p.add_argument("--check-config-only", action="store_true")
    p.add_argument("--json", action="store_true", dest="as_json")
    args = p.parse_args()

    payload = build_payload(args)
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
