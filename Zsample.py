import os
import pandas as pd
import zipfile
import tempfile
import shutil
import csv


def preprocess(input_paths: list) -> list:
    if isinstance(input_paths, str):
        input_paths = [input_paths]

    zip_path = input_paths[0]

    if not zip_path.lower().endswith(".zip"):
        raise ValueError(f"Expected a ZIP file, received: {zip_path}")

    target_dir = os.path.dirname(zip_path) or "."
    temp_dir = tempfile.mkdtemp()

    filings_path = None
    amendments_path = None
    output_paths = []

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)

                if not filename:
                    continue

                lower_name = filename.lower()

                # Skip unwanted files
                if lower_name.endswith((".sql", ".rtf")):
                    continue

                # Extract filings.txt
                if lower_name == "filings.txt":
                    filings_path = os.path.join(temp_dir, filename)
                    with zip_ref.open(member) as src, open(filings_path, "wb") as dst:
                        dst.write(src.read())
                    continue

                # Extract filingamendments.txt
                if lower_name == "filingamendments.txt":
                    amendments_path = os.path.join(target_dir, filename)
                    with zip_ref.open(member) as src, open(amendments_path, "wb") as dst:
                        dst.write(src.read())
                    output_paths.append(amendments_path)
                    continue

                # Extract other files
                target_path = os.path.join(target_dir, filename)
                with zip_ref.open(member) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())

                output_paths.append(target_path)

        if not filings_path or not amendments_path:
            raise ValueError(
                "Required input files Filings.txt or FilingAmendments.txt not found in ZIP"
            )

        # Read amendments
        amendments = pd.read_csv(
            amendments_path,
            sep=",",
            dtype=str,
            encoding="utf-8",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            engine="python",
            usecols=["FileNumber", "AmendmentType"]
        ).drop_duplicates(
            subset=["FileNumber"],
            keep="last"
        )

        # Read filings
        filings = pd.read_csv(
            filings_path,
            sep=",",
            dtype=str,
            encoding="utf-8",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            engine="python"
        )

        # Merge
        merged = filings.merge(
            amendments,
            on="FileNumber",
            how="left"
        )

        # Reorder columns
        cols = merged.columns.tolist()
        if "Type" in cols and "AmendmentType" in cols:
            idx = cols.index("Type")
            cols.insert(idx + 1, cols.pop(cols.index("AmendmentType")))
            merged = merged[cols]

        # Save output
        processed_path = os.path.join(target_dir, "filings_processed.txt")
        merged.to_csv(
            processed_path,
            sep=",",
            index=False,
            encoding="utf-8",
            quoting=csv.QUOTE_ALL
        )

        output_paths.append(processed_path)
        return output_paths

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# # Entry point
# if __name__ == "__main__":
#     input_paths_loc = r"C:\Users\chennai\OneDrive - Dun and Bradstreet\Desktop\Migration_UCC\AR\Sample_10000.zip"
#     result = preprocess(input_paths_loc)
#     print(f"Output: {result}")