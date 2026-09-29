import os
import re
import uuid
from typing import Any, Optional

import cloudinary
import cloudinary.exceptions
import cloudinary.uploader
from dotenv import load_dotenv
from PIL import Image


load_dotenv()

cloudinary.config(
	cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
	api_key=os.getenv("CLOUDINARY_API_KEY"),
	api_secret=os.getenv("CLOUDINARY_API_SECRET"),
	secure=True,
)


def store_profile_image(
	image: Any,
	user_id: Optional[str] = None,
) -> dict:
	"""Upload and store a user's profile image in Cloudinary."""
	if getattr(image, "size", 0) > 5 * 1024 * 1024:
		raise ValueError("Image must be smaller than 5 MB.")

	try:
		image.seek(0)
		with Image.open(image) as uploaded_image:
			uploaded_image.verify()
		image.seek(0)
	except (OSError, ValueError):
		raise ValueError("Please upload a valid image file.")

	upload_options = {
		"folder": "MarketSphere/profiles",
		"resource_type": "image",
		"overwrite": True,
		"invalidate": True,
		"transformation": [{
			"width": 400,
			"height": 400,
			"crop": "fill",
			"gravity": "face",
			"quality": "auto",
			"fetch_format": "auto",
		}],
	}

	if user_id:
		upload_options["public_id"] = f"profile_{user_id}"

	return cloudinary.uploader.upload(image, **upload_options)


def store_seller_asset(
	file: Any,
	seller_id: str,
	asset_type: str,
	resource_type: str = "auto",
) -> dict:
	"""Upload a seller-owned image or document into the seller's Cloudinary folder."""
	if getattr(file, "size", 0) > 20 * 1024 * 1024:
		raise ValueError("Seller files must be smaller than 20 MB.")

	asset_type = re.sub(r"[^a-zA-Z0-9_-]", "_", str(asset_type)).strip("_")
	if not asset_type:
		raise ValueError("Invalid seller file type.")

	content_type = (getattr(file, "content_type", "") or "").lower()
	try:
		file.seek(0)
		if content_type.startswith("image/"):
			with Image.open(file) as uploaded_image:
				uploaded_image.verify()
		elif content_type == "application/pdf":
			if file.read(5) != b"%PDF-":
				raise ValueError("Please upload a valid PDF file.")
		file.seek(0)
	except (OSError, ValueError):
		raise ValueError("Please upload a valid seller file.")

	upload_options = {
		"folder": f"MarketSphere/sellers/{seller_id}/{asset_type}",
		"public_id": asset_type,
		"resource_type": resource_type,
		"overwrite": True,
		"invalidate": True,
	}
	if resource_type == "image":
		upload_options["transformation"] = [{
			"width": 1600,
			"height": 900,
			"crop": "limit",
			"quality": "auto",
			"fetch_format": "auto",
		}]

	result = cloudinary.uploader.upload(file, **upload_options)
	if not (result.get("secure_url") or result.get("url")):
		raise ValueError("Cloudinary did not return a URL for the seller file.")
	return result


def store_product_media(file: Any, product_id: str, media_type: str = "image") -> dict:
	"""Upload product images now and videos later using the same Cloudinary API."""
	if media_type not in {"image", "video"}:
		raise ValueError("Unsupported product media type.")
	if getattr(file, "size", 0) > 50 * 1024 * 1024:
		raise ValueError("Product media must be smaller than 50 MB.")

	content_type = (getattr(file, "content_type", "") or "").lower()
	if media_type == "image":
		try:
			file.seek(0)
			with Image.open(file) as uploaded_image:
				uploaded_image.verify()
			file.seek(0)
		except (OSError, ValueError):
			raise ValueError("Please upload a valid product image.")
	elif not content_type.startswith("video/"):
		raise ValueError("Please upload a valid product video.")

	resource_type = "video" if media_type == "video" else "image"
	upload_options = {
		"folder": f"MarketSphere/products/{product_id}",
		"public_id": f"media_{uuid.uuid4().hex}",
		"resource_type": resource_type,
		"overwrite": False,
		"invalidate": True,
	}
	if media_type == "image":
		upload_options["transformation"] = [{
			"width": 2000,
			"height": 2000,
			"crop": "limit",
			"quality": "auto",
			"fetch_format": "auto",
		}]

	try:
		result = cloudinary.uploader.upload(file, **upload_options)
	except cloudinary.exceptions.NotAllowed as error:
		raise ValueError(
			"Cloudinary upload permission is missing. Please update the Cloudinary API key permissions."
		) from error
	except cloudinary.exceptions.Error as error:
		raise ValueError("Unable to upload product media to Cloudinary right now.") from error
	if not (result.get("secure_url") or result.get("url")):
		raise ValueError("Cloudinary did not return a URL for the product media.")
	return result


def store_catalog_image(file: Any, catalog_type: str, object_id: str, asset_type: str) -> dict:
	"""Upload a category or brand image into its Cloudinary catalog folder."""
	if getattr(file, "size", 0) > 10 * 1024 * 1024:
		raise ValueError("Catalog images must be smaller than 10 MB.")

	try:
		file.seek(0)
		with Image.open(file) as uploaded_image:
			uploaded_image.verify()
		file.seek(0)
	except (OSError, ValueError):
		raise ValueError("Please upload a valid catalog image.")

	upload_options = {
		"folder": f"MarketSphere/catalog/{catalog_type}/{object_id}",
		"public_id": asset_type,
		"resource_type": "image",
		"overwrite": True,
		"invalidate": True,
		"transformation": [{
			"width": 1600,
			"height": 1600,
			"crop": "limit",
			"quality": "auto",
			"fetch_format": "auto",
		}],
	}

	try:
		result = cloudinary.uploader.upload(file, **upload_options)
	except cloudinary.exceptions.NotAllowed as error:
		raise ValueError(
			"Cloudinary upload permission is missing. Please update the Cloudinary API key permissions."
		) from error
	except cloudinary.exceptions.Error as error:
		raise ValueError("Unable to upload catalog image to Cloudinary right now.") from error

	if not (result.get("secure_url") or result.get("url")):
		raise ValueError("Cloudinary did not return a URL for the catalog image.")
	return result


def store_promotion_image(file: Any, promotion_id: str, asset_type: str) -> dict:
	"""Upload a promotion banner or thumbnail to Cloudinary."""
	if getattr(file, "size", 0) > 10 * 1024 * 1024:
		raise ValueError("Promotion images must be smaller than 10 MB.")

	try:
		file.seek(0)
		with Image.open(file) as uploaded_image:
			uploaded_image.verify()
		file.seek(0)
	except (OSError, ValueError):
		raise ValueError("Please upload a valid promotion image.")

	if asset_type not in {"banner", "thumbnail"}:
		raise ValueError("Invalid promotion image type.")

	upload_options = {
		"folder": f"MarketSphere/promotions/{promotion_id}",
		"public_id": asset_type,
		"resource_type": "image",
		"overwrite": True,
		"invalidate": True,
		"transformation": [{
			"width": 2000,
			"height": 1000 if asset_type == "banner" else 1000,
			"crop": "limit",
			"quality": "auto",
			"fetch_format": "auto",
		}],
	}

	try:
		result = cloudinary.uploader.upload(file, **upload_options)
	except cloudinary.exceptions.NotAllowed as error:
		raise ValueError(
			"Cloudinary upload permission is missing. Please update the Cloudinary API key permissions."
		) from error
	except cloudinary.exceptions.Error as error:
		raise ValueError("Unable to upload promotion image to Cloudinary right now.") from error

	if not (result.get("secure_url") or result.get("url")):
		raise ValueError("Cloudinary did not return a URL for the promotion image.")
	return result
