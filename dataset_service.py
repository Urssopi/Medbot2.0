import os
import re
from typing import Any

from openpyxl import load_workbook


class DeidentifiedDataset:
    def __init__(self, candidate_paths: list[str]) -> None:
        self.candidate_paths = candidate_paths
        self.records: list[dict[str, Any]] = []
        self.path: str = ""

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        return re.sub(r"\s+", " ", text).strip()

    def _tokenize(self, text: str) -> set[str]:
        return set(re.findall(r"[a-z]{3,}", text.lower()))

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."

    def _select_path(self) -> str:
        for candidate in self.candidate_paths:
            if os.path.exists(candidate):
                return candidate
        return ""

    def load(self) -> tuple[bool, str]:
        dataset_path = self._select_path()
        if not dataset_path:
            self.records = []
            self.path = ""
            return False, "Dataset not found."

        wb = load_workbook(dataset_path, read_only=True, data_only=True)
        sheet_name = "INCIDENTS" if "INCIDENTS" in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet_name]

        rows = ws.iter_rows(min_row=1, values_only=True)
        headers = [self._clean_text(h) for h in next(rows)]
        col_idx = {name: idx for idx, name in enumerate(headers)}

        def get_value(row: tuple[Any, ...], key: str) -> str:
            idx = col_idx.get(key, -1)
            if idx < 0 or idx >= len(row):
                return ""
            return self._clean_text(row[idx])

        records: list[dict[str, Any]] = []
        for row in rows:
            encounter_id = get_value(row, "Encounter ID")
            chief_complaint = get_value(row, "Chief Complaint")
            illness_type = get_value(row, "Type of injury/Illness")
            body_part = get_value(row, "Body Part Involved")
            provisional = get_value(row, "Provisional Diagnosis")
            final_dx = get_value(row, "Final Diagnosis")
            plan = get_value(row, "Initial Plan")
            hpi = get_value(row, "HPI")

            summary = " | ".join(
                item
                for item in [
                    f"Encounter ID: {encounter_id}" if encounter_id else "",
                    f"Chief Complaint: {chief_complaint}" if chief_complaint else "",
                    f"Type: {illness_type}" if illness_type else "",
                    f"Body Part: {body_part}" if body_part else "",
                    f"Provisional Dx: {provisional}" if provisional else "",
                    f"Final Dx: {final_dx}" if final_dx else "",
                    f"Plan: {self._truncate(plan, 240)}" if plan else "",
                    f"HPI: {self._truncate(hpi, 220)}" if hpi else "",
                ]
                if item
            )

            token_source = " ".join(
                [chief_complaint, illness_type, body_part, provisional, final_dx, plan, hpi]
            )
            records.append(
                {
                    "encounter_id": encounter_id,
                    "chief_complaint": chief_complaint,
                    "final_dx": final_dx,
                    "summary": summary,
                    "tokens": self._tokenize(token_source),
                }
            )

        self.records = records
        self.path = dataset_path
        return True, f"Loaded {len(records)} cases from dataset."

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_tokens = self._tokenize(query)
        if not self.records or not query_tokens:
            return []

        scored: list[tuple[int, dict[str, Any]]] = []
        for record in self.records:
            overlap = len(query_tokens.intersection(record["tokens"]))
            if overlap <= 0:
                continue
            scored.append((overlap, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        result: list[dict[str, Any]] = []
        for score, record in scored[:top_k]:
            item = dict(record)
            item["score"] = score
            result.append(item)
        return result

    def build_context(self, matches: list[dict[str, Any]]) -> str:
        if not matches:
            return "No close matching reference cases found in the local de-identified dataset."
        lines: list[str] = []
        for idx, row in enumerate(matches, start=1):
            lines.append(f"{idx}. {row['summary']}")
        return "\n".join(lines)
