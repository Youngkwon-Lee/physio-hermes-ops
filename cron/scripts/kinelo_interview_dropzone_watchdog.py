#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

GOOGLE_API_PATH = Path(os.environ.get("GOOGLE_API_PATH", str(Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py")))
OUTPUT_DIR = Path(os.environ.get("KINELO_INTERVIEW_OUTPUT_DIR", Path.home() / "kinelo/interviews"))
MANIFEST_DIR = Path(os.environ.get("KINELO_INTERVIEW_MANIFEST_DIR", str(Path.home() / "physio-hermes-ops/dashboard/runtime/automation_job_manifests")))
DRIVE_ROOT_NAME = os.environ.get("KINELO_DRIVE_ROOT_NAME", "Kinelo Ops")
MEETING_FOLDER_NAME = os.environ.get("KINELO_DRIVE_MEETING_FOLDER", "05_미팅원본")
INCOMING_FOLDER_NAME = os.environ.get("KINELO_DRIVE_INCOMING_FOLDER", "_incoming")
JOB_ID = "7a55d26ff570"
JOB_NAME = "매시 Kinelo 인터뷰 폴더 확인"
Json = dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(UTC)


def load_google_api(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("google_api", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load google api helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def drive_service() -> Any:
    return load_google_api(GOOGLE_API_PATH).build_service("drive", "v3")


def drive_search(service: Any, query: str, page_size: int = 20) -> list[Json]:
    result = service.files().list(
        q=query,
        pageSize=page_size,
        fields="files(id,name,mimeType,modifiedTime,webViewLink,parents)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return result.get("files", [])


def ensure_folder(service: Any, name: str, parent_id: str | None = None) -> Json:
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query = f"{query} and '{parent_id}' in parents"
    matches = drive_search(service, query, 5)
    if matches:
        return matches[0]
    body: Json = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    return service.files().create(body=body, fields="id,name,webViewLink,parents", supportsAllDrives=True).execute()


def flow_roots(service: Any) -> Json:
    kinelo_root = ensure_folder(service, DRIVE_ROOT_NAME)
    meeting_root = ensure_folder(service, MEETING_FOLDER_NAME, kinelo_root["id"])
    incoming_root = ensure_folder(service, INCOMING_FOLDER_NAME, meeting_root["id"])
    return {"kinelo": kinelo_root, "meeting": meeting_root, "incoming": incoming_root}


def download_file(service: Any, file_id: str, out_path: Path) -> Path:
    request = service.files().get_media(fileId=file_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with io.FileIO(str(out_path), "wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return out_path


def read_json_file(service: Any, file_id: str) -> Json:
    with tempfile.TemporaryDirectory(prefix="kinelo-meta-") as tmp_dir:
        path = download_file(service, file_id, Path(tmp_dir) / "metadata.json")
        return json.loads(path.read_text(encoding="utf-8"))


def move_to_parent(service: Any, file_id: str, new_parent_id: str) -> Json:
    meta = service.files().get(fileId=file_id, fields="id,name,parents,webViewLink", supportsAllDrives=True).execute()
    parents = meta.get("parents", []) or []
    if new_parent_id in parents and len(parents) == 1:
        return meta
    return service.files().update(
        fileId=file_id,
        addParents=new_parent_id,
        removeParents=",".join(parents),
        fields="id,name,parents,webViewLink",
        supportsAllDrives=True,
    ).execute()


def upload_text_file(service: Any, name: str, content: str, parent_id: str, mime_type: str) -> Json:
    query = f"name = '{name}' and '{parent_id}' in parents and trashed = false"
    matches = drive_search(service, query, 5)
    media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype=mime_type, resumable=False)
    if matches:
        return service.files().update(
            fileId=matches[0]["id"], media_body=media, fields="id,name,webViewLink,parents", supportsAllDrives=True
        ).execute()
    return service.files().create(
        body={"name": name, "parents": [parent_id]}, media_body=media, fields="id,name,webViewLink,parents", supportsAllDrives=True
    ).execute()


def note_frontmatter(metadata: Json, audio_file: Json) -> list[str]:
    summary = metadata.get("summary") or f"{metadata['customerName']} 인터뷰 요약을 여기에 정리하세요."
    fields = [
        ("title", f"{metadata['customerName']} Interview Feedback"),
        ("kind", "meeting-note"),
        ("layer", "operations"),
        ("status", "active"),
        ("schema", "customer-interview-ingest-v1"),
        ("meeting_date", metadata["meetingDate"]),
        ("customer_name", metadata["customerName"]),
        ("account_name", metadata["accountName"]),
        ("owner", "이영권"),
        ("source_thread_id", metadata.get("threadId") or "TODO"),
        ("source_thread_title", metadata.get("threadTitle") or "TODO"),
        ("source_workspace", "hermes-home-desktop"),
        ("source_audio_mode", "voice-recording"),
        ("raw_drive_file_id", audio_file.get("id", "")),
        ("raw_drive_file_name", audio_file.get("name", "")),
        ("raw_drive_web_view_link", audio_file.get("webViewLink", "")),
        ("key_issue", metadata.get("keyIssue") or "TODO: 인터뷰 후 핵심 이슈 1문장 정리"),
        ("current_workflow", metadata.get("currentWorkflow") or "TODO: 현재 운영 방식 요약"),
        ("target_workflow", metadata.get("targetWorkflow") or "TODO: 목표 운영 방식 요약"),
        ("next_action", metadata.get("nextAction") or "TODO: 다음 액션 1개 정리"),
        ("summary", summary),
    ]
    return [
        "---",
        *(f"{key}: {value}" for key, value in fields),
        "tags:",
        "  - kinelo",
        "  - customer-interview",
        f"  - {metadata.get('slug', 'customer-interview')}",
        "---",
    ]


def build_note(metadata: Json, audio_file: Json, note_path: Path) -> str:
    lines = [
        *note_frontmatter(metadata, audio_file),
        f"# {metadata['customerName']} 인터뷰 피드백", "",
        "## Context", "- 인터뷰 목적과 상황을 2~3줄로 정리", "",
        "## Participants", f"- {metadata['customerName']} ({metadata['accountName']})", "- 이영권", "",
        "## Key points", "- ", "",
        "## Decisions", "- [결정] - 이유:", "",
        "## Open questions", "- ", "",
        "## Next actions", "- [ ] owner: due:", "",
        "## Links", f"- raw audio: {audio_file.get('webViewLink', 'TODO')}", f"- note path: {note_path}", "",
    ]
    return "\n".join(lines)


def artifact_for_path(label: str, path: str) -> Json:
    file_path = Path(path)
    artifact: Json = {"label": label, "kind": "interview-note", "path": str(file_path)}
    if file_path.exists():
        stat = file_path.stat()
        artifact["modifiedAt"] = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
        artifact["sizeBytes"] = stat.st_size
    return artifact


def write_manifest(started_at: datetime, result: Json) -> None:
    errors = [item.get("error", str(item)) for item in result.get("errors", [])]
    created_files = [artifact_for_path(item.get("customer") or item.get("notePath") or "interview note", item["notePath"]) for item in result.get("processed", []) if item.get("notePath")]
    payload = {
        "schemaVersion": 1,
        "evidenceSource": "runtime-direct",
        "generatedAt": utc_now().isoformat(),
        "runStartedAt": started_at.isoformat(),
        "runFinishedAt": utc_now().isoformat(),
        "status": "error" if errors else "ok",
        "job": {"id": JOB_ID, "name": JOB_NAME, "runtime": "hermes-script"},
        "createdFiles": created_files,
        "notionPages": [],
        "discordMessages": [],
        "artifacts": created_files,
        "errors": errors,
        "metadata": {"incomingCount": result.get("incomingCount", 0), "metadataCandidates": result.get("metadataCandidates", 0), "processedCount": len(result.get("processed", [])), "errorCount": len(result.get("errors", [])), "processed": result.get("processed", []), "unmatched": result.get("unmatched", [])},
    }
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MANIFEST_DIR / f"{JOB_ID}.json"
    tmp_path = manifest_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(manifest_path)


def process_pair(service: Any, roots: Json, metadata_file: Json, audio_file: Json) -> Json:
    metadata = read_json_file(service, metadata_file["id"])
    meeting_date = metadata["meetingDate"]
    monthly_folder = ensure_folder(service, meeting_date[:7], roots["meeting"]["id"])
    with tempfile.TemporaryDirectory(prefix="kinelo-audio-") as tmp_dir:
        download_file(service, audio_file["id"], Path(tmp_dir) / audio_file["name"])
    moved_audio = move_to_parent(service, audio_file["id"], monthly_folder["id"])
    moved_metadata = move_to_parent(service, metadata_file["id"], monthly_folder["id"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = metadata.get("slug", metadata_file["name"].removesuffix(".json"))
    note_name = f"{meeting_date}-{slug}.md"
    note_path = OUTPUT_DIR / note_name
    note_text = build_note(metadata, moved_audio, note_path)
    note_path.write_text(note_text, encoding="utf-8")
    note_drive = upload_text_file(service, note_name, note_text, monthly_folder["id"], "text/markdown")
    receipt_payload = {
        "ok": True,
        "processedAt": utc_now().isoformat(),
        "metadataFileId": moved_metadata.get("id", ""),
        "audioFileId": moved_audio.get("id", ""),
        "noteFileId": note_drive.get("id", ""),
        "noteName": note_name,
        "audioLink": moved_audio.get("webViewLink", ""),
        "noteLink": note_drive.get("webViewLink", ""),
    }
    receipt_name = metadata_file["name"].replace(".json", ".ingested.json")
    receipt_drive = upload_text_file(service, receipt_name, json.dumps(receipt_payload, ensure_ascii=False, indent=2), monthly_folder["id"], "application/json")
    return {"customer": metadata.get("customerName", ""), "meetingDate": meeting_date, "audioFile": moved_audio.get("name", ""), "audioLink": moved_audio.get("webViewLink", ""), "metadataFile": moved_metadata.get("name", ""), "notePath": str(note_path), "noteDriveLink": note_drive.get("webViewLink", ""), "receiptDriveLink": receipt_drive.get("webViewLink", "")}


def collect_incoming(service: Any, roots: Json) -> Json:
    incoming_files = drive_search(service, f"'{roots['incoming']['id']}' in parents and trashed = false", 100)
    file_map = {item["name"]: item for item in incoming_files if item.get("name")}
    processed: list[Json] = []
    errors: list[Json] = []
    unmatched: list[Json] = []
    metadata_candidates = 0
    for metadata_file in sorted(incoming_files, key=lambda item: item.get("name", "")):
        name = metadata_file.get("name", "")
        if not name.endswith(".json") or name.endswith(".ingested.json"):
            continue
        metadata_candidates += 1
        try:
            metadata = read_json_file(service, metadata_file["id"])
            expected_audio = metadata.get("expectedAudioFile") or f"{name[:-5]}.m4a"
            audio_file = file_map.get(expected_audio)
            if audio_file:
                processed.append(process_pair(service, roots, metadata_file, audio_file))
            else:
                unmatched.append({"metadataFile": name, "expectedAudioFile": expected_audio})
        except Exception as exc:
            errors.append({"metadataFile": name, "error": str(exc)})
    return {
        "ok": len(errors) == 0,
        "incomingCount": len(incoming_files),
        "metadataCandidates": metadata_candidates,
        "processed": processed,
        "errors": errors,
        "unmatched": unmatched[:50],
    }


def main() -> int:
    started_at = utc_now()
    service = drive_service()
    roots = flow_roots(service)
    result = collect_incoming(service, roots)
    write_manifest(started_at, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
