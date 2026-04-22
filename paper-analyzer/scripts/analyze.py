#!/usr/bin/env python3
"""
Paper Analyzer - Entry point for paper/code analysis
Supports both paper mode (arXiv) and code-only mode
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

def download_arxiv_html(arxiv_id: str, output_dir: str) -> tuple[str, list[str]]:
    """Download arXiv paper as HTML and extract embedded images

    Returns:
        tuple of (html_path, list of downloaded image paths)
    """
    html_url = f"https://arxiv.org/abs/{arxiv_id}"
    output_path = os.path.join(output_dir, f"{arxiv_id}.html")
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    print(f"Downloading paper HTML: {html_url}")

    result = subprocess.run(
        ["wget", "-q", "-O", output_path, html_url],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        result = subprocess.run(
            ["curl", "-s", "-o", output_path, html_url],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Download failed: {result.stderr}")

    print(f"Saved to: {output_path}")

    # Extract image URLs from HTML
    with open(output_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Find all image URLs (arxiv CDN images)
    img_pattern = r'src="(https://[^"]*\.arxiv\.org[^"]*\.(?:png|jpg|jpeg|gif|png\S*))"'
    img_urls = re.findall(img_pattern, html_content)

    # Also find dataicke URLs
    img_pattern2 = r'src="(https://[^"]*dataicke[^"]*\.(?:png|jpg|jpeg|gif))"'
    img_urls.extend(re.findall(img_pattern2, html_content))

    img_urls = list(set(img_urls))  # deduplicate
    downloaded_images = []

    for i, img_url in enumerate(img_urls):
        img_ext = os.path.splitext(img_url)[1] or '.png'
        img_name = f"fig_{i+1}{img_ext}"
        img_path = os.path.join(images_dir, img_name)

        print(f"Downloading image: {img_url}")
        result = subprocess.run(
            ["wget", "-q", "-O", img_path, img_url],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["curl", "-s", "-o", img_path, img_url],
                capture_output=True,
                text=True
            )
        if result.returncode == 0:
            downloaded_images.append(img_path)
            print(f"  -> {img_path}")

    # Write manifest of images to process
    manifest_path = os.path.join(output_dir, "image_manifest.txt")
    with open(manifest_path, 'w') as f:
        f.write(f"TOTAL_IMAGES: {len(downloaded_images)}\n")
        for i, img_path in enumerate(downloaded_images):
            f.write(f"IMAGE_{i+1}: {img_path}\n")

    print(f"\n=== IMAGE MANIFEST ===")
    print(f"Total images found: {len(downloaded_images)}")
    print(f"Manifest: {manifest_path}")
    print(f"========================\n")

    return output_path, downloaded_images

def clone_repository(url: str, output_dir: str) -> str:
    """Clone GitHub repository using git"""
    print(f"Cloning repository: {url}")

    # Extract repo path from URL
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
        # Determine mode
        mode = args.mode
        if mode == "auto":
            if "github.com" in args.input.lower():
                mode = "code"
            else:
                mode = "paper"

        # Resolve output_dir - if relative path given, use current working directory
        output_dir = os.path.abspath(args.output_dir)

        if mode == "paper":
            arxiv_id = parse_arxiv_id(args.input)
            print(f"Parsed arXiv ID: {arxiv_id}")

            # Create output directory: paper-analyzer-output/{arxiv-id}/
            paper_output_dir = os.path.join(output_dir, f"paper-analyzer-output", arxiv_id)
            os.makedirs(paper_output_dir, exist_ok=True)

            html_path, downloaded_images = download_arxiv_html(arxiv_id, paper_output_dir)

            print(f"\n=== ANALYZER_READY ===")
            print(f"MODE: paper")
            print(f"HTML_PATH: {html_path}")
            print(f"OUTPUT_DIR: {paper_output_dir}")
            print(f"IMAGE_COUNT: {len(downloaded_images)}")
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
