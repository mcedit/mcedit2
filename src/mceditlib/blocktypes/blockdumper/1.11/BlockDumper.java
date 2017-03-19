package net.mcedit;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;

import net.minecraft.util.NonNullList;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import net.minecraft.block.Block;
import net.minecraft.block.material.Material;
import net.minecraft.block.state.IBlockState;
import net.minecraft.client.renderer.BlockModelShapes;
import net.minecraft.client.renderer.block.statemap.BlockStateMapper;
import net.minecraft.client.renderer.block.model.ModelManager;
import net.minecraft.client.renderer.block.model.ModelResourceLocation;
import net.minecraft.creativetab.CreativeTabs;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;

public class BlockDumper extends Block {
	private static final Logger logger = LogManager.getLogger();

	public BlockDumper(Material par2Material) {
		super(par2Material);
		// TODO Auto-generated constructor stub
	}

	static String join(Collection<String> s, String delimiter) {
		StringBuilder builder = new StringBuilder();
		Iterator<String> iter = s.iterator();
		while (iter.hasNext()) {
			builder.append(iter.next());
			if (!iter.hasNext()) {
				break;
			}
			builder.append(delimiter);
		}
		return builder.toString();
	}

	public static void dump(ModelManager modelManager) {
		BlockModelShapes shapes = modelManager.getBlockModelShapes();
		BlockStateMapper mapper = shapes.getBlockStateMapper();
		Map<IBlockState, ModelResourceLocation> stateMap = mapper.putAllStateModelLocations();
		HashSet<String> seenStates = new HashSet<String>();
		try {
			// -- open streams --

			FileOutputStream idMappingStream = new FileOutputStream(new File("idmapping_raw_1_11.json"));
			PrintWriter idMappingWriter = new PrintWriter(idMappingStream);
			idMappingWriter.print("[\n");

			FileOutputStream blockDumpStream = new FileOutputStream(new File("minecraft_raw_1_11.json"));
			PrintWriter wri = new PrintWriter(blockDumpStream);
			wri.format("[\n");

			FileOutputStream hiddenStatesStream = new FileOutputStream(new File("hiddenstates_1_11.json"));
			PrintWriter hiddenStatesWriter = new PrintWriter(hiddenStatesStream);
			hiddenStatesWriter.print("[\n");

			ArrayList<String> hiddens = new ArrayList<String>();

			ArrayList<String> idMapping = new ArrayList<String>();
			ArrayList<String> blocks = new ArrayList<String>();
			for (Block b : Block.REGISTRY) {
				int id = Block.REGISTRY.getIDForObject(b);
				ArrayList<String> attrs = new ArrayList<String>();
				String internalName = Block.REGISTRY.getNameForObject(b).toString();
				IBlockState defaultState = b.getDefaultState();
				for (Object vso : b.getBlockState().getValidStates()) {
					IBlockState vs = (IBlockState) vso;
					ModelResourceLocation mrl = (ModelResourceLocation) stateMap.get(vs);
					if (vs != null && mrl != null)
						hiddens.add(String.format(
								"{\"blockState\":\"%s\", \"resourcePath\": \"%s\", \"resourceVariant\": \"%s\"}",
								vs.toString(), mrl.getResourcePath(), mrl.getVariant()));

				}
				attrs.add(String.format("\"internalName\": \"%s\"", internalName));

				CreativeTabs creativeTabToDisplayOn = b.getCreativeTabToDisplayOn();
				if (creativeTabToDisplayOn != null) {
					attrs.add(String.format("\"creativeTab\": \"%s\"", creativeTabToDisplayOn.getTabLabel()));
				}

				attrs.add(String.format("\"opaqueCube\": %s", defaultState.isOpaqueCube()));
				attrs.add(String.format("\"collidable\": %s", b.isCollidable()));
				attrs.add(String.format("\"hasEntity\": %s", b.hasTileEntity()));
				attrs.add(String.format("\"opacity\": %s", defaultState.getLightOpacity()));
				attrs.add(String.format("\"brightness\": %s", defaultState.getLightValue()));
				attrs.add(String.format("\"useNeighborBrightness\": %s", defaultState.useNeighborBrightness()));
				attrs.add(String.format("\"renderLayer\": \"%s\"", b.getBlockLayer()));

				NonNullList<ItemStack> subBlocks = NonNullList.func_191196_a();
				Map<Integer, ItemStack> subBlocksByMeta = new HashMap<Integer, ItemStack>();
				ItemStack i;
				try {
					i = b.getItem(null, null, defaultState);
					b.getSubBlocks(i.getItem(), null, subBlocks);

					for (ItemStack stack : subBlocks) {
						int itemMeta = stack.getMetadata();
						subBlocksByMeta.put(itemMeta, stack);
					}
				} catch (Exception e) {
					logger.warn(String.format("Failed to get subBlocks for block %s (error was %s)", b, e));
					e.printStackTrace();
				}

				int defaultMeta = b.getMetaFromState(defaultState);
				boolean hasItems = false;
				for (int meta = 0; meta < 16; meta++) {
					ArrayList<String> metaAttrs = (ArrayList<String>) attrs.clone();
					try {
						IBlockState bs = b.getStateFromMeta(meta);
						String bsString = bs.toString();
						if (seenStates.contains(bsString)) {
							continue;
						}
						seenStates.add(bsString);

						idMapping.add(String.format("[%d, %d, \"%s\"]", id, meta, bsString));

						if (meta == defaultMeta) {
							metaAttrs.add("\"defaultState\": 1");
						}

						metaAttrs.add(String.format("\"materialMapColor\": %d", bs.getMapColor().colorValue));
						metaAttrs.add(String.format("\"blockState\": \"%s\"", bs.toString()));
						metaAttrs.add(String.format("\"renderType\": %d", bs.getRenderType().ordinal()));
						ModelResourceLocation loc = stateMap.get(bs);
						if (loc != null) {
							metaAttrs.add(String.format("\"resourcePath\": \"%s\"", loc.getResourcePath()));
							metaAttrs.add(String.format("\"resourceVariant\": \"%s\"", loc.getVariant()));

						}

						/*
						 * block names aren't displayed so not all blocks
						 * have a localizedName. we have to go through the
						 * ItemStack for a displayName
						 */
						ItemStack stack = subBlocksByMeta.get(meta);
						try {
							metaAttrs.add(String.format("\"unlocalizedName\": \"%s\"", stack.getUnlocalizedName()));
							metaAttrs.add(String.format("\"displayName\": \"%s\"", stack.getDisplayName()));
							hasItems = true;
						} catch (NullPointerException e) {
							metaAttrs.add(String.format("\"unlocalizedName\": \"%s\"", b.getUnlocalizedName()));
							metaAttrs.add(String.format("\"displayName\": \"%s\"", b.getLocalizedName()));

						}
						blocks.add("{" + join(metaAttrs, ", ") + "}");

					} catch (Exception e) {
						logger.warn(String.format("Failed to get meta %d for block %s (error was %s)", meta, b, e));
						e.printStackTrace();
					}
				}

			}

			idMappingWriter.println(join(idMapping, ",\n"));
			idMappingWriter.format("]\n");
			idMappingWriter.close();
			wri.println(join(blocks, ",\n"));
			wri.format("]\n");
			wri.close();
			blockDumpStream.close();

			hiddenStatesWriter.println(join(hiddens, ",\n"));
			hiddenStatesWriter.format("]\n");
			hiddenStatesWriter.close();



		} catch (FileNotFoundException e) {
		} catch (IOException e) {

		}
	}
	// private static void addIcons(Block b, int damage, ArrayList<String>
	// attrs) {
	// for (int j = 0; j < 6; j++) {
	// Icon icon = b.getIcon(j, damage);
	// if(icon != null) {
	// attrs.add(String.format("\"iconName%d\": \"%s\"", j,
	// icon.getIconName()));
	// }
	// }
	// }
}
