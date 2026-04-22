#!/usr/bin/env python3
"""
Paper Analyzer - Entry point for paper/code analysis
Supports both paper mode (arXiv PDF) and code-only mode
Uses wget/curl for all network requests
"""

import re
import sys
import os
import subprocess
import argparse

def parse_arxiv_id(link: str) -> str:
    """Extract arXiv ID from link or validate standalone ID"""
    patterns = [
        r'arxiv\.org/abs/([0-9]+\.[0-9]+)',
        r'arxiv\.org/html/([0-9]+\.[0-9]+)',
        r'arxiv\.org/pdf/([0-9]+\.[0-9]+)',
        r'^([0-9]+\.[0-9]+)$',
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    raise ValueError(f"Cannot parse arXiv ID from: {link}")

def download_arxiv_pdf(arxiv_id: str, output_dir: str) -> tuple[str, str]:
    """Download arXiv paper as PDF and extract text/images

    Returns:
        tuple of (pdf_path, text_path)
    """
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    pdf_path = os.path.join(output_dir, f"{arxiv_id}.pdf")
    text_path = os.path.join(output_dir, f"{arxiv_id}.txt")
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    print(f"Downloading paper PDF: {pdf_url}")

    result = subprocess.run(
        ["wget", "-q", "-O", pdf_path, pdf_url],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        result = subprocess.run(
            ["curl", "-s", "-o", pdf_path, pdf_url],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"PDF download failed: {result.stderr}")

    print(f"Downloaded to: {pdf_path}")

    # Extract text from PDF using pdftotext
    print("Extracting text from PDF...")
    result = subprocess.run(
        ["pdftotext", "-q", pdf_path, text_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Warning: pdftotext failed: {result.stderr}")
        # Try with layout preservation
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, text_path],
            capture_output=True,
            text=True
        )
    print(f"Text extracted to: {text_path}")

    # Extract images from PDF using pdftoppm
    print("Extracting images from PDF...")
    img_base = os.path.join(images_dir, "fig")
    result = subprocess.run(
        ["pdftoppm", "-png", "-r", "150", pdf_path, img_base],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Warning: pdftoppm failed: {result.stderr}")

    # Count extracted images
    extracted_images = sorted([
        f for f in os.listdir(images_dir)
        if f.startswith("fig") and f.endswith(".png")
    ])

    print(f"Extracted {len(extracted_images)} images to {images_dir}/")

    # Write manifests
    manifest_path = os.path.join(output_dir, "image_manifest.txt")
    with open(manifest_path, 'w') as f:
        f.write(f"TOTAL_IMAGES: {len(extracted_images)}\n")
        for i, img in enumerate(extracted_images):
            img_path = os.path.join(images_dir, img)
            f.write(f"IMAGE_{i+1}: {img_path}\n")

    # Write page count and basic info
    info_path = os.path.join(output_dir, "paper_info.txt")
    result = subprocess.run(
        ["pdfinfo", pdf_path],
        capture_output=True,
        text=True
    )
    page_count = 0
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if line.startswith('Pages:'):
                page_count = int(line.split(':')[1].strip())
                break

    with open(info_path, 'w') as f:
        f.write(f"ARXIV_ID: {arxiv_id}\n")
        f.write(f"PAGES: {page_count}\n")
        f.write(f"PDF_PATH: {pdf_path}\n")
        f.write(f"TEXT_PATH: {text_path}\n")
        f.write(f"TOTAL_IMAGES: {len(extracted_images)}\n")

    print(f"\n=== PAPER MANIFEST ===")
    print(f"arXiv ID: {arxiv_id}")
    print(f"Pages: {page_count}")
    print(f"Total images: {len(extracted_images)}")
    print(f"PDF: {pdf_path}")
    print(f"Text: {text_path}")
    print(f"Images: {images_dir}/")
    print(f"========================\n")

    return pdf_path, text_path

def clone_repository(url: str, output_dir: str) -> str:
    """Clone GitHub repository using git"""
    print(f"Cloning repository: {url}")

    match = re.search(r'github\.com[/:](.+?)(?:\.git)?$', url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {url}")

    repo_name = match.group(1).split('/')[-1]
    output_path = os.path.join(output_dir, repo_name)

    result = subprocess.run(
        ["git", "clone", "--quiet", url, output_path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr}")

    print(f"Cloned to: {output_path}")
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Paper Analyzer")
    parser.add_argument("input", help="arXiv link/ID or GitHub URL")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--mode", choices=["paper", "code", "auto"], default="auto",
                        help="Analysis mode: paper (arXiv), code (GitHub only), or auto")
    parser.add_argument("--deep", action="store_true", default=True, help="Deep analysis mode")
    parser.add_argument("--no-agent", action="store_true", help="Disable automatic subAgent")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"], help="Output language")

    args = parser.parse_args()

    try:
        mode = args.mode
        if mode == "auto":
            if "github.com" in args.input.lower():
                mode = "code"
            else:
                mode = "paper"

        output_dir = os.path.abspath(args.output_dir)

        if mode == "paper":
            arxiv_id = parse_arxiv_id(args.input)
            print(f"Parsed arXiv ID: {arxiv_id}")

            paper_output_dir = os.path.join(output_dir, f"paper-analyzer-output", arxiv_id)
            os.makedirs(paper_output_dir, exist_ok=True)

            pdf_path, text_path = download_arxiv_pdf(arxiv_id, paper_output_dir)

            # Count images
            images_dir = os.path.join(paper_output_dir, "images")
            img_count = len([f for f in os.listdir(images_dir) if f.startswith("fig") and f.endswith(".png")]) if os.path.exists(images_dir) else 0

            print(f"\n=== ANALYZER_READY ===")
            print(f"MODE: paper")
            print(f"PDF_PATH: {pdf_path}")
            print(f"TEXT_PATH: {text_path}")
            print(f"OUTPUT_DIR: {paper_output_dir}")
            print(f"IMAGE_COUNT: {img_count}")
            print(f"ARXIV_ID: {arxiv_id}")
            print(f"DEEP_MODE: {args.deep}")
            print(f"AUTO_AGENT: {not args.no_agent}")
            print(f"LANG: {args.lang}")
            print(f"=== ANALYZER_READY ===")

        else:  # code mode
            repo_path = clone_repository(args.input, args.output_dir)

            print(f"\n=== ANALYZER_READY ===")
            print(f"MODE: code")
            print(f"REPO_PATH: {repo_path}")
            print(f"REPO_URL: {args.input}")
            print(f"OUTPUT_DIR: {output_dir}")
            print(f"DEEP_MODE: {args.deep}")
            print(f"AUTO_AGENT: {not args.no_agent}")
            print(f"LANG: {args.lang}")
            print(f"=== ANALYZER_READY ===")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()