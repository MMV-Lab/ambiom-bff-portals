from pathlib import Path
import shutil
from tqdm import tqdm
import jpype
import scyjava

try:
	scyjava.config.endpoints.append('ome:formats-gpl:latest')
	scyjava.start_jvm()
	loci = jpype.JPackage("loci")
	loci.common.DebugTools.setRootLevel("WARN")
	print("Bio-Formats logging level set to WARN.")

except ImportError:
	print("Could not import jpype or scyjava. Make sure they are installed.")
except jpype.JException as e:
	print(f"An error occurred while trying to configure Java logging: {e}")

from bioio import BioImage
import bioio_bioformats
from bioio.writers.ome_tiff_writer import OmeTiffWriter
from bioio.writers.ome_zarr_writer import OmeZarrWriter


# nohup python3 Final.py > output.log 2>&1 &

# ----------- Configuration -----------
input_path = Path("AG29").expanduser().resolve()
output_path = Path("./output/AG-29_Anika/NEW").resolve()
tmp_path = Path("./tmp").resolve()

# Set to a glob pattern (e.g. "250319_Knee2_*") or None to process all
name_to_match = "221031_AG-029_A1_zoom12-1_z5_16-53-36"
# name_to_match = None

# Set to True if you want to perform conversion
convert = True

# -------------------------------------


output_path.mkdir(parents=True, exist_ok=True)
tmp_path.mkdir(parents=True, exist_ok=True)

# Clear tmp before starting
tqdm.write("🧹 Clearing temporary directory... ")
for f in tmp_path.glob("*"):
	if f.is_file():
		try:
			f.unlink()
		except OSError as e:
			tqdm.write(f"Warning: Could not delete temporary file {f}: {e}")
tqdm.write("✅ Temporary directory cleared.")


# Get subdirectories to process
if name_to_match:
	sub_dirs = [p for p in sorted(
		input_path.glob(name_to_match)) if p.is_dir()]
else:
	sub_dirs = [p for p in sorted(input_path.iterdir()) if p.is_dir()]

if not sub_dirs:
	print("❌ No subdirectories found to process.")
	exit()

# Process each subdirectory with tqdm
for sub_dir in tqdm(sub_dirs, desc="🔍 Processing samples", unit="sample"):
	sample_name = sub_dir.name
	#out_file = output_path / f"{sample_name}"
	

	ome_files = sorted(sub_dir.rglob("*.ome.tif"))
	if not ome_files:
		tqdm.write(f"⚠️ No OME-TIFF files in {sub_dir.name}, skipping...")
		continue
	else:
		tqdm.write(f"Found {len(ome_files)} files for {sample_name}")

	# Check if all found files are in the same directory
	all_in_same_dir = False
	first_parent_dir = None
	if len(ome_files) > 0:
		first_parent_dir = ome_files[0].parent
		all_in_same_dir = all(
			Path(f).parent == first_parent_dir for f in ome_files)

	path_to_read = None
	needs_tmp_cleanup = False  # Flag to track if tmp was used for this sample

	if not (convert):
		tqdm.write(
			f"⏭️ Skipping processing/saving for {sample_name} as copy_and_save is False.")
		for file in tqdm(ome_files, desc=f"📥 Inspecting {sample_name}", unit="file", leave=False):
			tqdm.write(f"Found file: {file.name}")

	if convert:
		if all_in_same_dir:
			tqdm.write(
				f"✅ All {len(ome_files)} files for {sample_name} are in the same directory: {first_parent_dir}. Reading directly.")
			# Read the first file from its original location
			path_to_read = ome_files[0]
			needs_tmp_cleanup = False
		else:

			tqdm.write(
				f"⚠️ Files for {sample_name} are scattered. Copying to temporary directory.")
			for file in tqdm(ome_files, desc=f"📥 Copying {sample_name}", unit="file", leave=False):
				try:
					shutil.copy(file, tmp_path / file.name)
				except Exception as e:
					tqdm.write(f"❌ Failed to copy {file.name}: {e}")

			tmp_files = sorted(tmp_path.glob("*.ome.tif"))
			if not tmp_files:
				tqdm.write("⚠️ No files found in tmp after attempting copy.")
				continue

			path_to_read = tmp_files[0]
			needs_tmp_cleanup = True

		if path_to_read and path_to_read.exists():
			tqdm.write(
				f"🧠 Reading: {path_to_read.name} (from {path_to_read.parent})")
			try:
				img = BioImage(path_to_read, reader=bioio_bioformats.Reader)

			except Exception as e:
				tqdm.write(f"❌ Failed to read image {path_to_read.name}: {e}")

			tqdm.write(f"💾 Saving processed image in {output_path}")
			try:
				# Build necessary OME metadata structure for the single image output

				out_file = output_path / f"{sample_name}.ome.tif"

				# single_image_ome = OmeTiffWriter.build_ome(
				# 	[img.shape],
				# 	[img.dtype],
				# 	[img.dims.order],
				# 	[img.channel_names],
				# 	[str(out_file.name)],
				# 	[img.physical_pixel_sizes]
				# )
    
				single_image_ome = OmeTiffWriter.build_ome(
					[(img.shape[1], img.shape[0], *img.shape[2:])],
					[img.dtype],
					['CTZYX'],
					[img.channel_names],
					[str(out_file.name)],
					[img.physical_pixel_sizes]
				)

				out_ome = img.ome_metadata.model_copy()
				
				# Override image
				out_ome.images = single_image_ome.images
    
				# reconstreuct manufacturer ??
				out_ome.images[0].annotation_refs = img.ome_metadata.images[0].annotation_refs
				out_ome.images[0].acquisition_date = img.ome_metadata.images[0].acquisition_date
				out_ome.images[0].description = img.ome_metadata.images[0].description

				order = single_image_ome.images[0].pixels.dimension_order.value
				order = order[::-1]
				# Save to OME TIFF
				OmeTiffWriter.save(
					img.get_image_dask_data(order),
					out_file,
					dim_order=order,
					ome_xml=out_ome
				)
			
				tqdm.write(f"✅ Successfully saved OME TIFF to: {out_file.name}")

				out_file = output_path / f"{sample_name}.ome.zarr"
				# Save to OME ZARR
				zarr_writer = OmeZarrWriter(out_file)
				zarr_writer.write_image(
					image_data=img.get_image_dask_data("CZYX"),
					image_name=out_file.name,
					physical_pixel_sizes=img.physical_pixel_sizes,
					channel_names=img.channel_names,
					channel_colors=None,
					scale_num_levels=4,
					scale_factor=2
				)

				tqdm.write(f"✅ Successfully saved OME ZARR to: {out_file.name}")
			
			except Exception as e:
				tqdm.write(f"❌ Failed to save image {out_file.name}: {e}")
				if out_file.exists():
					try:
						out_file.unlink()
						tqdm.write(
							f"🧹 Removed potentially corrupted output file {out_file.name}")
					except OSError as rm_err:
						tqdm.write(
							f"⚠️ Could not remove failed output file {out_file.name}: {rm_err}")
				continue
		else:
			tqdm.write(
				f"❌ Logic error: No valid file path determined for reading for sample {sample_name}.")

			needs_tmp_cleanup = True

	if needs_tmp_cleanup:
		tqdm.write(f"🧹 Cleaning up temporary file(s) for {sample_name}...")
		for f in tmp_path.glob("*"):
			if f.is_file():
				try:
					f.unlink()
				except OSError as e:
					tqdm.write(
						f"Warning: Could not delete temporary file {f}: {e}")
		tqdm.write("✅ Temporary directory cleared.")

tqdm.write("\n✅ All processing complete.")

if jpype.isJVMStarted():
	jpype.shutdownJVM()
