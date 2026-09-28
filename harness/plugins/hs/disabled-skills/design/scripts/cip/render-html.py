#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIP HTML Presentation Renderer

Generates a professional HTML presentation from CIP mockup images
with detailed descriptions, concepts, and brand guidelines.
"""

import argparse
import base64
import sys
from datetime import datetime
from pathlib import Path

import jinja2

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))
from core import search, get_cip_brief

# Deliverable descriptions for presentation
DELIVERABLE_INFO = {
    "business card": {
        "title": "Business Card",
        "concept": "First impression touchpoint for professional networking",
        "purpose": "Creates memorable brand recall during business exchanges",
        "specs": "Standard 3.5 x 2 inches, premium paper stock"
    },
    "letterhead": {
        "title": "Letterhead",
        "concept": "Official correspondence identity",
        "purpose": "Establishes credibility and professionalism in written communications",
        "specs": "A4/Letter size, digital and print versions"
    },
    "document template": {
        "title": "Document Template",
        "concept": "Branded document system for internal and external use",
        "purpose": "Ensures consistent brand representation across all documents",
        "specs": "Multiple formats: Word, PDF, Google Docs compatible"
    },
    "reception signage": {
        "title": "Reception Signage",
        "concept": "Brand presence in physical office environment",
        "purpose": "Creates strong first impression for visitors and reinforces brand identity",
        "specs": "3D dimensional letters, backlit LED options, premium materials"
    },
    "office signage": {
        "title": "Office Signage",
        "concept": "Wayfinding and brand presence system",
        "purpose": "Guides visitors while maintaining consistent brand experience",
        "specs": "Modular system with directional and informational signs"
    },
    "polo shirt": {
        "title": "Polo Shirt",
        "concept": "Professional team apparel",
        "purpose": "Creates unified team identity and brand ambassadorship",
        "specs": "Premium pique cotton, embroidered logo on left chest"
    },
    "t-shirt": {
        "title": "T-Shirt",
        "concept": "Casual brand apparel",
        "purpose": "Extends brand reach through everyday wear and promotional events",
        "specs": "High-quality cotton, screen print or embroidery options"
    },
    "vehicle": {
        "title": "Vehicle Branding",
        "concept": "Mobile brand advertising",
        "purpose": "Transforms fleet into moving billboards for maximum visibility",
        "specs": "Partial or full wrap, vinyl graphics, weather-resistant"
    },
    "van": {
        "title": "Van Branding",
        "concept": "Commercial vehicle identity",
        "purpose": "Professional fleet presence for service and delivery operations",
        "specs": "Full wrap design, high-visibility contact information"
    },
    "car": {
        "title": "Car Branding",
        "concept": "Executive vehicle identity",
        "purpose": "Professional presence for corporate and sales teams",
        "specs": "Subtle branding, door panels and rear window"
    },
    "envelope": {
        "title": "Envelope",
        "concept": "Branded mail correspondence",
        "purpose": "Extends brand identity to all outgoing mail",
        "specs": "DL, C4, C5 sizes with logo placement"
    },
    "folder": {
        "title": "Presentation Folder",
        "concept": "Document organization with brand identity",
        "purpose": "Professional presentation of proposals and materials",
        "specs": "A4/Letter pocket folder with die-cut design"
    }
}

# Page shell template. Loops/conditionals/inheritance were the signed buy reason
# (string.Template has none); this file only needed the loop (one card per deliverable)
# — no cross-page inheritance to share, single page. autoescape=True is a deliberate
# CHANGE from the old f-string version, not a byte-identical requirement: brand_name
# flows straight from --brand (CLI-controlled) into <title>/<h1>/the footer with zero
# hand-escaping today — `--brand 'X<script>...'` lands live in the page. Jinja2's
# default escaping closes that; see harness/tests for the pinned before/after.
# CSS braces are plain (no f-string {{ }} doubling needed in a Jinja2 template).
# {% for %}/{% endfor %} sit on their own line (trim_blocks+lstrip_blocks eats the tag
# line whole) with one blank line kept INSIDE the loop body so every card — including
# the first and the one before </section> — keeps the blank-line gap the old per-card
# string-concat produced; verified byte-for-byte against the pre-conversion renderer.
_TEMPLATE_SRC = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ brand_name }} - Corporate Identity Program</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0a0a0a;
            color: #ffffff;
            line-height: 1.6;
        }
        .hero {
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 4rem 2rem;
            background: linear-gradient(135deg, #1a1a2e 0%, #0a0a0a 100%);
        }
        .hero h1 {
            font-size: 4rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #ffffff 0%, #888888 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero .subtitle {
            font-size: 1.5rem;
            color: #888;
            margin-bottom: 3rem;
        }
        .hero .meta {
            display: flex;
            gap: 3rem;
            flex-wrap: wrap;
            justify-content: center;
        }
        .hero .meta-item {
            text-align: center;
        }
        .hero .meta-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #666;
            margin-bottom: 0.5rem;
        }
        .hero .meta-value {
            font-size: 1rem;
            color: #ccc;
        }
        .section {
            padding: 6rem 2rem;
            max-width: 1400px;
            margin: 0 auto;
        }
        .section-title {
            font-size: 2.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #fff;
        }
        .section-subtitle {
            font-size: 1.1rem;
            color: #888;
            margin-bottom: 4rem;
            max-width: 600px;
        }
        .deliverable {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4rem;
            margin-bottom: 8rem;
            align-items: center;
        }
        .deliverable:nth-child(even) {
            direction: rtl;
        }
        .deliverable:nth-child(even) > * {
            direction: ltr;
        }
        .deliverable-image {
            position: relative;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .deliverable-image img {
            width: 100%;
            height: auto;
            display: block;
        }
        .deliverable-content {
            padding: 2rem 0;
        }
        .deliverable-title {
            font-size: 2rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #fff;
        }
        .deliverable-concept {
            font-size: 1.1rem;
            color: #aaa;
            margin-bottom: 1.5rem;
            font-style: italic;
        }
        .deliverable-purpose {
            font-size: 1rem;
            color: #888;
            margin-bottom: 1.5rem;
            line-height: 1.8;
        }
        .deliverable-specs {
            display: inline-block;
            padding: 0.5rem 1rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            font-size: 0.85rem;
            color: #666;
        }
        .color-palette {
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
        }
        .color-swatch {
            width: 60px;
            height: 60px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .footer {
            text-align: center;
            padding: 4rem 2rem;
            border-top: 1px solid #222;
            color: #666;
        }
        .footer p {
            margin-bottom: 0.5rem;
        }
        @media (max-width: 900px) {
            .hero h1 {
                font-size: 2.5rem;
            }
            .deliverable {
                grid-template-columns: 1fr;
                gap: 2rem;
            }
            .deliverable:nth-child(even) {
                direction: ltr;
            }
        }
    </style>
</head>
<body>
    <section class="hero">
        <h1>{{ brand_name }}</h1>
        <p class="subtitle">Corporate Identity Program</p>
        <div class="meta">
            <div class="meta-item">
                <div class="meta-label">Industry</div>
                <div class="meta-value">{{ industry_display }}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Style</div>
                <div class="meta-value">{{ style_name }}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Mood</div>
                <div class="meta-value">{{ mood }}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Deliverables</div>
                <div class="meta-value">{{ deliverables|length }} Items</div>
            </div>
        </div>
    </section>

    <section class="section">
        <h2 class="section-title">Brand Applications</h2>
        <p class="section-subtitle">
            Comprehensive identity system designed to maintain consistency
            across all brand touchpoints and communications.
        </p>

{% for d in deliverables %}
        <div class="deliverable">
            <div class="deliverable-image">
                <img src="{{ d.img_src }}" alt="{{ d.title }}" loading="lazy">
            </div>
            <div class="deliverable-content">
                <h3 class="deliverable-title">{{ d.title }}</h3>
                <p class="deliverable-concept">{{ d.concept }}</p>
                <p class="deliverable-purpose">{{ d.purpose }}</p>
                <span class="deliverable-specs">{{ d.specs }}</span>
            </div>
        </div>

{% endfor %}
    </section>

    <footer class="footer">
        <p><strong>{{ brand_name }}</strong> Corporate Identity Program</p>
        <p>Generated on {{ generated_date }}</p>
        <p style="margin-top: 1rem; font-size: 0.8rem;">Powered by CIP Design Skill</p>
    </footer>
</body>
</html>
"""

_ENV = jinja2.Environment(
    loader=jinja2.DictLoader({"presentation.html": _TEMPLATE_SRC}),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def get_image_base64(image_path):
    """Convert image to base64 for embedding in HTML"""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"Warning: Could not load image {image_path}: {e}")
        return None


def get_deliverable_info(filename):
    """Extract deliverable type from filename and get info"""
    filename_lower = filename.lower()
    for key, info in DELIVERABLE_INFO.items():
        if key.replace(" ", "-") in filename_lower or key.replace(" ", "_") in filename_lower:
            return info
    # Default info
    return {
        "title": filename.replace("-", " ").replace("_", " ").title(),
        "concept": "Brand identity application",
        "purpose": "Extends brand presence across touchpoints",
        "specs": "Custom specifications"
    }


def generate_html(brand_name, industry, images_dir, output_path=None, style=None):
    """Generate HTML presentation from CIP images"""

    images_dir = Path(images_dir)
    if not images_dir.exists():
        print(f"Error: Directory not found: {images_dir}")
        return None

    # Get all PNG images
    images = sorted(images_dir.glob("*.png"))
    if not images:
        print(f"Error: No PNG images found in {images_dir}")
        return None

    # Get CIP brief for brand info
    brief = get_cip_brief(brand_name, industry, style)
    style_info = brief.get("style", {})
    industry_info = brief.get("industry", {})

    # Build one context dict per deliverable — the loop the template now owns.
    deliverables = []
    for image_path in images:
        info = get_deliverable_info(image_path.stem)
        img_base64 = get_image_base64(image_path)
        img_src = f"data:image/png;base64,{img_base64}" if img_base64 else str(image_path)
        deliverables.append({
            "img_src": img_src,
            "title": info["title"],
            "concept": info["concept"],
            "purpose": info["purpose"],
            "specs": info["specs"],
        })

    html_content = _ENV.get_template("presentation.html").render(
        brand_name=brand_name,
        industry_display=industry_info.get("Industry", industry.title()),
        style_name=style_info.get("Style Name", "Corporate"),
        mood=style_info.get("Mood", "Professional"),
        deliverables=deliverables,
        generated_date=datetime.now().strftime("%B %d, %Y"),
    )

    # Save HTML
    output_path = output_path or images_dir / f"{brand_name.lower().replace(' ', '-')}-cip-presentation.html"
    output_path = Path(output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ HTML presentation generated: {output_path}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Generate HTML presentation from CIP mockups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate HTML from CIP images directory
  python render-html.py --brand "TopGroup" --industry "consulting" --images ./topgroup-cip

  # Specify output path
  python render-html.py --brand "TopGroup" --industry "consulting" --images ./cip --output presentation.html
        """
    )

    parser.add_argument("--brand", "-b", required=True, help="Brand name")
    parser.add_argument("--industry", "-i", default="technology", help="Industry type")
    parser.add_argument("--style", "-s", help="Design style")
    parser.add_argument("--images", required=True, help="Directory containing CIP mockup images")
    parser.add_argument("--output", "-o", help="Output HTML file path")

    args = parser.parse_args()

    generate_html(
        brand_name=args.brand,
        industry=args.industry,
        images_dir=args.images,
        output_path=args.output,
        style=args.style
    )


if __name__ == "__main__":
    main()
