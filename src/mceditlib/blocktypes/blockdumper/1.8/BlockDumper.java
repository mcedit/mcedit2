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
import java.util.Set;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import net.minecraft.block.Block;
import net.minecraft.block.material.Material;
import net.minecraft.block.state.BlockState;
import net.minecraft.block.state.IBlockState;
import net.minecraft.client.renderer.BlockModelShapes;
import net.minecraft.client.renderer.block.statemap.BlockStateMapper;
import net.minecraft.client.resources.model.ModelManager;
import net.minecraft.client.resources.model.ModelResourceLocation;
import net.minecraft.creativetab.CreativeTabs;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.util.ResourceLocation;

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
		Map stateMap = mapper.enumerateBlocks();
		try {
			// -- open streams --

			FileOutputStream idMappingStream = new FileOutputStream(new File("idmapping_raw.json"));
			PrintWriter idMappingWriter = new PrintWriter(idMappingStream);
			idMappingWriter.print("[\n");

			FileOutputStream blockDumpStream = new FileOutputStream(new File("minecraft_raw.json"));
			PrintWriter wri = new PrintWriter(blockDumpStream);
			wri.format("[\n");

			ArrayList<String> idMapping = new ArrayList<String>();
			ArrayList<String> blocks = new ArrayList<String>();
			for (Object o : Block.blockRegistry) {
				int id = Block.blockRegistry.getIDForObject(o);
				Block b = (Block) o;
				ArrayList<String> attrs = new ArrayList<String>();
				if (b != null) {
					String internalName = Block.blockRegistry.getNameForObject(b).toString();
					attrs.add(String.format("\"internalName\": \"%s\"", internalName));

					attrs.add(String.format("\"color\": %s", b.getBlockColor()));

					CreativeTabs creativeTabToDisplayOn = b.getCreativeTabToDisplayOn();
					if (creativeTabToDisplayOn != null) {
						attrs.add(String.format("\"creativeTab\": \"%s\"", creativeTabToDisplayOn.getTabLabel()));
					}

					Material m = b.getMaterial();

					attrs.add(String.format("\"materialBlocksMovement\": %s", m.blocksMovement()));
					attrs.add(String.format("\"materialBurns\": %s", m.getCanBurn()));
					attrs.add(String.format("\"materialMobility\": %s", m.getMaterialMobility()));
					attrs.add(String.format("\"materialLiquid\": %s", m.isLiquid()));
					attrs.add(String.format("\"materialOpaque\": %s", m.isOpaque()));
					attrs.add(String.format("\"materialReplacable\": %s", m.isReplaceable()));
					attrs.add(String.format("\"materialSolid\": %s", m.isSolid()));

					attrs.add(String.format("\"opaqueCube\": %s", b.isOpaqueCube()));
					attrs.add(String.format("\"collidable\": %s", b.isCollidable()));
					attrs.add(String.format("\"hasEntity\": %s", b.hasTileEntity()));
					attrs.add(String.format("\"opacity\": %s", b.getLightOpacity()));
					attrs.add(String.format("\"brightness\": %s", b.getLightValue()));
					attrs.add(String.format("\"useNeighborBrightness\": %s", b.getUseNeighborBrightness()));

					attrs.add(String.format("\"renderType\": %s", b.getRenderType()));
					attrs.add(String.format("\"color\": %s", b.getBlockColor()));

					attrs.add(String.format("\"minx\": %s", b.getBlockBoundsMinX()));
					attrs.add(String.format("\"miny\": %s", b.getBlockBoundsMinY()));
					attrs.add(String.format("\"minz\": %s", b.getBlockBoundsMinZ()));
					attrs.add(String.format("\"maxx\": %s", b.getBlockBoundsMaxX()));
					attrs.add(String.format("\"maxy\": %s", b.getBlockBoundsMaxY()));
					attrs.add(String.format("\"maxz\": %s", b.getBlockBoundsMaxZ()));

					ArrayList<ItemStack> subBlocks = new ArrayList<ItemStack>();
					Map<Integer, ItemStack> subBlocksByMeta = new HashMap<Integer, ItemStack>();
					Item i = null;
					try {
						i = b.getItem(null, null);
						b.getSubBlocks(i, null, subBlocks);

						for (ItemStack stack : subBlocks) {
							ArrayList<String> subAttrs = new ArrayList<String>();
							int itemDamage = stack.getItemDamage();
							int itemMeta = stack.getMetadata();
							subBlocksByMeta.put(itemMeta, stack);
						}
					} catch (Exception e) {
						logger.warn(String.format("Failed to get subBlocks for block %s (error was %s)", b, e));
						e.printStackTrace();
					}

					IBlockState defaultState = b.getDefaultState();
					HashSet<String> seenStates = new HashSet<String>();
					int defaultMeta = b.getMetaFromState(defaultState);
					boolean hasItems = false;
					for (int meta = 0; meta < 16; meta++) {
						ArrayList<String> metaAttrs = (ArrayList<String>) attrs.clone();
						try {
							IBlockState bs = b.getStateFromMeta(meta);
							String bsString = bs.toString();
							if(seenStates.contains(bsString)) {
								continue;
							}
							seenStates.add(bsString);

							idMapping.add(String.format("[%d, %d, \"%s\"]", id, meta, bsString));

							if (meta == defaultMeta) {
								metaAttrs.add("\"defaultState\": 1");
							}

							metaAttrs.add(String.format("\"materialMapColor\": %d", b.getMapColor(bs).colorValue));
							metaAttrs.add(String.format("\"blockState\": \"%s\"", bs.toString()));
							metaAttrs.add(String.format("\"renderType\": %d", b.getRenderType()));
							ModelResourceLocation loc = (ModelResourceLocation) stateMap.get(bs);
							if (loc != null) {
								metaAttrs.add(String.format("\"resourcePath\": \"%s\"", loc.getResourcePath()));
								metaAttrs.add(String.format("\"resourceVariant\": \"%s\"", loc.getResourceVariant()));

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

					// if (!hasItems) {
					// attrs.add("\"defaultState\": 1");
					// attrs.add(String.format("\"blockState\": \"%s\"",
					// b.getDefaultState().toString()));
					// attrs.add(String.format("\"unlocalizedName\": \"%s\"",
					// b.getUnlocalizedName()));
					// attrs.add(String.format("\"displayName\": \"%s\"",
					// b.getLocalizedName()));
					// ModelResourceLocation loc = (ModelResourceLocation)
					// stateMap.get(defaultState);
					// if (loc != null) {
					// String resPath = loc.getResourcePath();
					// attrs.add(String.format("\"resourcePath\": \"%s\"",
					// resPath));
					// }
					// blocks.add("{" + join(attrs, ", ") + "}");
					// }

				}

			}
			idMappingWriter.println(join(idMapping, ",\n"));
			idMappingWriter.format("]\n");
			idMappingWriter.close();
			wri.println(join(blocks, ",\n"));
			wri.format("]\n");
			wri.close();
			blockDumpStream.close();
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
