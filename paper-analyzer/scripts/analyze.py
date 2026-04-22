#!/usr/bin/env python3
"""
Paper Analyzer - Entry point for paper/code analysis
Supports both paper mode (arXiv PDF) and code-only mode
Uses wget/curl for all network requests

Two-stage image extraction:
1. Full-page low-res images for layout analysis
2. High-res cropped images for detailed analysis (after vision model identifies boxes)
"""

import re
import sys
import os
import subprocess
import argparse
import json
import xml.etree.ElementTree as ET

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

def download_arxiv_pdf(arxiv_id: str, output_dir: str) -> tuple[str, str, int]:
    """Download arXiv paper as PDF and extract text/images

    Returns:
        tuple of (pdf_path, text_path, page_count)
    """
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    pdf_path = os.path.join(output_dir, f"{arxiv_id}.pdf")
    text_path = os.path.join(output_dir, f"{arxiv_id}.txt")

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
        ["pdftotext", "-q", "-layout", pdf_path, text_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Warning: pdftotext failed, trying without layout...")
        result = subprocess.run(
            ["pdftotext", "-q", pdf_path, text_path],
            capture_output=True,
            text=True
        )
    print(f"Text extracted to: {text_path}")

    # Get page count
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

    print(f"PDF has {page_count} pages")

    # Create directories
    full_pages_dir = os.path.join(output_dir, "full_pages")
    crops_dir = os.path.join(output_dir, "crops")
    os.makedirs(full_pages_dir, exist_ok=True)
    os.makedirs(crops_dir, exist_ok=True)

    # Extract full-page low-res images (150 DPI for layout analysis)
    print("Extracting full-page images (low-res for layout)...")
    img_base = os.path.join(full_pages_dir, "page")
    result = subprocess.run(
        ["pdftoppm", "-png", "-r", "150", "-f", "1", "-l", str(page_count), pdf_path, img_base],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Warning: pdftoppm failed: {result.stderr}")

    full_pages = sorted([
        f for f in os.listdir(full_pages_dir)
        if f.startswith("page") and f.endswith(".png")
    ])

    print(f"Extracted {len(full_pages)} full-page images to {full_pages_dir}/")

    # Extract PDF structure for figure/table positions
    print("Extracting PDF structure (figure/table positions)...")
    pdf_struct_path = os.path.join(output_dir, "pdf_structure.json")
    extract_pdf_structure(pdf_path, pdf_struct_path, page_count)

    # Write manifests
    manifest_path = os.path.join(output_dir, "page_manifest.txt")
    with open(manifest_path, 'w') as f:
        f.write(f"TOTAL_PAGES: {page_count}\n")
        f.write(f"TOTAL_FULL_PAGES: {len(full_pages)}\n")
        for i, page_file in enumerate(full_pages):
            page_path = os.path.join(full_pages_dir, page_file)
            f.write(f"PAGE_{i+1}: {page_path}\n")

    # Write paper info
    info_path = os.path.join(output_dir, "paper_info.txt")
    with open(info_path, 'w') as f:
        f.write(f"ARXIV_ID: {arxiv_id}\n")
        f.write(f"PAGES: {page_count}\n")
        f.write(f"PDF_PATH: {pdf_path}\n")
        f.write(f"TEXT_PATH: {text_path}\n")
        f.write(f"FULL_PAGES_DIR: {full_pages_dir}\n")
        f.write(f"CROPS_DIR: {crops_dir}\n")
        f.write(f"FULL_PAGE_COUNT: {len(full_pages)}\n")
        f.write(f"PDF_STRUCTURE: {pdf_struct_path}\n")

    print(f"\n=== PAPER MANIFEST ===")
    print(f"arXiv ID: {arxiv_id}")
    print(f"Pages: {page_count}")
    print(f"Full pages: {len(full_pages)}")
    print(f"PDF: {pdf_path}")
    print(f"Text: {text_path}")
    print(f"Structure: {pdf_struct_path}")
    print(f"========================\n")

    return pdf_path, text_path, page_count


def extract_pdf_structure(pdf_path: str, output_path: str, page_count: int):
    """Extract PDF structure including figure/table positions using pdfimages"""
    structure = {
        "pages": [],
        "images": [],
        "figures": [],
        "tables": []
    }

    # Use pdfimages -list to get image info
    result = subprocess.run(
        ["pdfimages", "-list", pdf_path],
        capture_output=True,
        text=True
    )

    images = []
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        # Skip header lines
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 8:
                try:
                    img_info = {
                        "index": int(parts[0]),
                        "width": int(parts[1]),
                        "height": int(parts[2]),
                        "color": parts[3],
                        "comp": int(parts[4]),
                        "bpc": int(parts[5]),
                        "enc": parts[6],
                        "obj": parts[7],
                        "page": int(parts[8]) if len(parts) > 8 else 1
                    }
                    images.append(img_info)
                except (ValueError, IndexError):
                    continue

    structure["images"] = images

    # Use pdftext or pdfinfo for layout info
    # Also extract potential figure/table captions from text
    result = subprocess.run(
        ["pdftotext", "-layout", pdf_path, "-"],
        capture_output=True,
        text=True
    )

    text = result.stdout if result.returncode == 0 else ""

    # Find figure and table captions
    fig_pattern = r'(Fig(?:ure)?\.?\s*\d+[:\.]?\s*[^\n]+)'
    tab_pattern = r'(Tab(?:le)?\.?\s*\d+[:\.]?\s*[^\n]+)'

    figures = re.findall(fig_pattern, text, re.IGNORECASE)
    tables = re.findall(tab_pattern, text, re.IGNORECASE)

    structure["figure_captions"] = figures
    structure["table_captions"] = tables

    # Page-level structure (approximate based on images per page)
    page_images = {}
    for img in images:
        page = img.get("page", 1)
        if page not in page_images:
            page_images[page] = []
        page_images[page].append(img["width"] * img["height"])

    structure["pages"] = [
        {
            "page_num": i + 1,
            "image_count": len(page_images.get(i + 1, [])),
            "image_sizes": page_images.get(i + 1, [])
        }
        for i in range(page_count)
    ]

    with open(output_path, 'w') as f:
        json.dump(structure, f, indent=2)


def crop_pdf_region(pdf_path: str, output_dir: str, crop_specs: list) -> list:
    """Crop high-resolution regions from PDF based on specifications

    crop_specs: list of dicts with keys:
        - page: 1-indexed page number
        - x0, y0: top-left coordinates (in points, from bottom-left)
        - x1, y1: bottom-right coordinates
        - name: identifier for the crop

    Returns: list of cropped image paths
    """
    crops_dir = os.path.join(output_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)

    cropped_paths = []

    for i, spec in enumerate(crop_specs):
        page = spec["page"]
        x0 = spec["x0"]
        y0 = spec["y0"]
        x1 = spec["x1"]
        y1 = spec["y1"]
        name = spec.get("name", f"crop_{i+1}")

        # Crop using pdftoppm with bounding box
        # Format: -f startpage -l endpage -r resolution -x -y -W -H
        width = x1 - x0
        height = y1 - y0

        output_base = os.path.join(crops_dir, name)

        # Use Ghostscript for precise cropping at high resolution (300 DPI)
        gs_cmd = [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=png16m",
            f"-r300",  # 300 DPI for high-res
            f"-dFIXEDMEDIA",
            f"-dPDFFitPage",
            "-dUseCropBox",
            f"-dDEVICEWIDTHPOINTS={width}",
            f"-dDEVICEHEIGHTPOINTS={height}",
            f"-dHorizontalMargin={x0}",
            f"-dVerticalMargin={y0}",
            f"-sOutputFile={output_base}.png",
            pdf_path
        ]

        # Simpler approach: use pdfcrop or direct approach
        # Actually use mutool or ghostscript with proper bbox
        crop_cmd = [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=png16m",
            "-dFirstPage=" + str(page),
            "-dLastPage=" + str(page),
            "-dTextAlphaBits=4",
            "-dGraphicsAlphaBits=4",
            f"-r300",
            f"-sOutputFile={output_base}_tmp.png",
            pdf_path
        ]

        # Use pdftoppm with crop via post-processing
        # First extract the page
        page_file = os.path.join(crops_dir, f"_page_{page}.png")
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", "300", "-f", str(page), "-l", str(page), pdf_path, page_file.replace(".png", "")],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and os.path.exists(page_file.replace(".png", "1.png")):
            page_img = page_file.replace(".png", "1.png")

            # Get image dimensions to convert PDF points to pixels
            # 72 points = 1 inch, so at 300 DPI: 72 points = 300 pixels
            # Scale factor = 300/72 ≈ 4.167
            scale = 300 / 72.0

            # Convert PDF coordinates to pixel coordinates
            px0 = int(x0 * scale)
            py0 = int(y0 * scale)
            px1 = int(x1 * scale)
            py1 = int(y1 * scale)

            # Crop using ImageMagick if available, else use Python PIL
            crop_result = subprocess.run(
                ["convert", page_img, "-crop", f"{px1-px0}x{py1-py0}+{px0}+{py0}", "+repage", f"{output_base}.png"],
                capture_output=True,
                text=True
            )

            if crop_result.returncode == 0 and os.path.exists(f"{output_base}.png"):
                cropped_paths.append(f"{output_base}.png")
                print(f"Cropped: {output_base}.png ({width:.1f}x{height:.1f} pts)")
            else:
                # Fallback: Python-based cropping
                try:
                    from PIL import Image
                    img = Image.open(page_img)
                    cropped = img.crop((px0, py0, px1, py1))
                    cropped.save(f"{output_base}.png")
                    cropped_paths.append(f"{output_base}.png")
                    print(f"Cropped: {output_base}.png ({width:.1f}x{height:.1f} pts)")
                except ImportError:
                    print(f"Warning: ImageMagick not found, using fallback")
                    # Just copy the page
                    import shutil
                    shutil.copy(page_img, f"{output_base}.png")
                    cropped_paths.append(f"{output_base}.png")

            # Clean up temp page
            try:
                os.remove(page_img)
            except:
                pass

    return cropped_paths


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

    # New: crop command
    parser.add_argument("--crop", action="store_true", help="Crop specific region from PDF")
    parser.add_argument("--page", type=int, help="Page number for crop")
    parser.add_argument("--bbox", help="Bounding box: x0,y0,x1,y1 (in PDF points)")

    args = parser.parse_args()

    try:
        mode = args.mode
        if mode == "auto":
            if "github.com" in args.input.lower():
                mode = "code"
            else:
                mode = "paper"

        output_dir = os.path.abspath(args.output_dir)

        # Crop mode: crop specific region from existing PDF
        if args.crop:
            if not args.page or not args.bbox:
                print("Error: --crop requires --page and --bbox", file=sys.stderr)
                sys.exit(1)

            # Find PDF in output_dir
            pdf_files = [f for f in os.listdir(output_dir) if f.endswith('.pdf')]
            if not pdf_files:
                print("Error: No PDF found in output_dir", file=sys.stderr)
                sys.exit(1)

            pdf_path = os.path.join(output_dir, pdf_files[0])
            x0, y0, x1, y1 = map(float, args.bbox.split(','))

            crops = crop_pdf_region(pdf_path, output_dir, [{
                "page": args.page,
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "name": f"crop_p{args.page}_{x0}_{y0}"
            }])

            print(f"\n=== CROP_RESULT ===")
            for c in crops:
                print(f"CROP: {c}")
            print(f"=== CROP_RESULT ===")
            return

        if mode == "paper":
            arxiv_id = parse_arxiv_id(args.input)
            print(f"Parsed arXiv ID: {arxiv_id}")

            paper_output_dir = os.path.join(output_dir, f"paper-analyzer-output", arxiv_id)
            os.makedirs(paper_output_dir, exist_ok=True)

            pdf_path, text_path, page_count = download_arxiv_pdf(arxiv_id, paper_output_dir)

            # Count full pages
            full_pages_dir = os.path.join(paper_output_dir, "full_pages")
            full_page_count = len([f for f in os.listdir(full_pages_dir) if f.startswith("page")]) if os.path.exists(full_pages_dir) else 0

            print(f"\n=== ANALYZER_READY ===")
            print(f"MODE: paper")
            print(f"PDF_PATH: {pdf_path}")
            print(f"TEXT_PATH: {text_path}")
            print(f"OUTPUT_DIR: {paper_output_dir}")
            print(f"FULL_PAGE_COUNT: {full_page_count}")
            print(f"PAGE_COUNT: {page_count}")
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