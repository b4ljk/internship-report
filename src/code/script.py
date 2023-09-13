import io
import os
import random
import typing as t
import uuid

from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.schemas.materials import GeneratedMaterial
from app.utils.s3_handler import upload_file_object

color_dict = {
    "#000000": "#FFFFFF",  # black
    "#FFFFFF": "#000000",  # white
    "#B20019": "#FFFFFF",  # red
    "#270B65": "#FFFFFF",  # blue
    "#158D34": "#FFFFFF",  # green
    "#D38A15": "#FFFFFF",  # orange
    "#F5F105": "#000000",  # yellow
    "#B7AC8B": "#FFFFFF",  # gold
}


def get_items_from_child_dir(loc: str):
    current_directory = os.getcwd()
    current_directory = f"{current_directory}/{loc}"
    items = os.listdir(current_directory)
    return items


FONTS = get_items_from_child_dir("app/feature/fonts")


def vertical_dimensions(*, lines, font, font_size, gaps):
    lines.reverse()
    max_char_width = 0
    for line in lines:
        for char in line:
            max_char_width = max(max_char_width, get_text_dimensions(char, font)[2])

    # first max function gets height of every letter and gets the max,
    # second max function gets the max of the length of each line
    longest_text = max(len(line) for line in lines)
    total_line_height = (
        max(get_text_dimensions(line, font)[3] - get_text_dimensions(line, font)[1] for line in lines) * longest_text
    )
    padding = 4 * gaps
    width = (font_size + gaps) * len(lines) + padding
    height = (font_size + gaps) * longest_text + padding
    return width, height


def horizontal_dimensions(*, lines, font, font_size, gaps):
    padding = 4 * gaps
    width = max(get_text_dimensions(line, font)[2] for line in lines) + padding
    height = (font_size + gaps) * len(lines) + padding
    return width, height


def get_text_dimensions(text, font):
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1), color=(0, 0, 0, 0)))
    return draw.textbbox((0, 0), text, font)


def shrink_text(width, height, img, max_width, max_height):
    aspect_ratio = width / height

    if width > max_width or height > max_height:
        if width > height:
            new_width = max_width
            new_height = int(new_width / aspect_ratio)
        else:
            new_height = max_height
            new_width = int(new_height * aspect_ratio)

        img = img.resize((new_width, new_height), Image.ANTIALIAS)
    return img


def preview_text(
    text: str,
    is_vertical: bool,
    color: str,
    bordered: bool,
    PPI: int,
    font_size: int,
    strokewidth: int,
    gaps=3,
):
    height = 0
    width = 0
    if not bordered:
        strokewidth = 0
    current_directory = os.path.dirname(os.path.abspath(__file__)) + "/fonts"
    font_path = os.path.join(current_directory, FONTS[1])

    font = ImageFont.truetype(font_path, size=font_size)

    font_list = get_items_from_child_dir("app/feature/fonts")

    lines = text.split("\n")
    if is_vertical:
        gaps = gaps // 2
        width, height = vertical_dimensions(
            lines=lines,
            font=font,
            font_size=font_size,
            gaps=gaps,
        )
    else:
        width, height = horizontal_dimensions(lines=lines, font=font, font_size=font_size, gaps=gaps)

    img = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if is_vertical:
        write_vertical(
            lines=lines,
            draw=draw,
            font=font,
            font_size=font_size,
            gaps=gaps,
            color=color,
            outline_color="white",
            strokewidth=strokewidth,
        )
    else:
        write_horizontal(
            lines=lines,
            draw=draw,
            font=font,
            font_size=font_size,
            gaps=gaps,
            color=color,
            outline_color="white",
            strokewidth=strokewidth,
        )

    img_data = io.BytesIO()
    dpi = PPI / 2.54
    img.save(img_data, format="PNG")
    img_data.seek(0)

    return StreamingResponse(img_data, media_type="image/png")


def write_vertical(*, lines, draw, font, font_size, gaps, color, outline_color, strokewidth):
    padding = gaps * 2
    gaps = gaps // 2
    y = gaps
    x = padding
    # char_width = max(get_text_dimensions(char, font)[2] for line in lines for char in line)
    for idx, line in enumerate(lines):
        box_w = max(get_text_dimensions(x, font)[2] - get_text_dimensions(x, font)[0] for x in line)
        for char_idx, char in enumerate(line):
            if char == "ー":
                char = "┃"
            alignment_val = (box_w - get_text_dimensions(char, font)[2]) / 2
            draw.text(
                (x + alignment_val, y),
                char,
                font=font,
                fill=color,
                stroke_fill=outline_color,
                stroke_width=strokewidth,
            )
            y += font_size
        x += font_size + gaps
        y = padding


def write_horizontal(*, lines, draw, font, font_size, gaps, color, outline_color, strokewidth):
    padding = gaps * 2
    y = gaps
    for line in lines:
        x = padding
        draw.text(
            (x, y),
            line,
            font=font,
            fill=color,
            spacing=gaps,
            stroke_fill=outline_color,
            stroke_width=strokewidth,
        )
        y += font_size + gaps


def pillow_text_generator(
    text: str,
    is_vertical: bool = True,
    bordered: bool = True,
    PPI: int = 300,
    font_size: int = 90,
    strokewidth: int = 3,
    job_number: int = None,
    text_type: str = "text_title",
    gaps=3,
    element=None,
) -> t.List[str]:
    if text_type == "text_title":
        start_index = -23
    else:
        start_index = -63
    result_list = []
    for each_font in FONTS:
        for color, outline_color in color_dict.items():
            if not bordered:
                strokewidth = 0
            current_directory = f"{os.path.dirname(os.path.abspath(__file__))}/fonts"
            font_location = os.path.join(current_directory, each_font)
            font = ImageFont.truetype(font_location, size=font_size)

            lines = text.split("\n")
            width = height = 0
            if is_vertical:
                width, height = vertical_dimensions(
                    lines=lines,
                    font=font,
                    font_size=font_size,
                    gaps=gaps,
                )
            else:
                width, height = horizontal_dimensions(lines=lines, font=font, font_size=font_size, gaps=gaps)

            img = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            if is_vertical:
                write_vertical(
                    lines=lines,
                    draw=draw,
                    font=font,
                    font_size=font_size,
                    gaps=gaps,
                    color=color,
                    outline_color=outline_color,
                    strokewidth=strokewidth,
                )
            else:
                write_horizontal(
                    lines=lines,
                    draw=draw,
                    font=font,
                    font_size=font_size,
                    gaps=gaps,
                    color=color,
                    outline_color=outline_color,
                    strokewidth=strokewidth,
                )

            saving_location = f"/jobs/{job_number}/input/png"
            text = text.replace(" ", "_")
            font_name = each_font.replace(".tff", "")
            file_name = f"{text_type}_created_{color}_{font_name}.png"

            if settings.IS_LOCAL:
                directory = f"/static{saving_location}"
                os.makedirs(directory, exist_ok=True)
                saved_location = f"{directory}/{file_name}"
                img.save(saved_location, "PNG", dpi=(PPI, PPI))
                material_file = GeneratedMaterial(
                    id=start_index,
                    png_width=img.width,
                    png_height=img.height,
                    index=job_number,
                    png_file_path=saved_location,
                    job_id=job_number,
                    element_id=element.id,
                    element_name=element.name,
                    element=element,
                    font_name=font_name,
                    color=color,
                )
                result_list.append(material_file)
            else:
                img_data = io.BytesIO()
                img.save(img_data, format="PNG")
                img_data.seek(0)
                saved_location = f"/static{saving_location}/{file_name}"
                upload_file_object(img_data, saved_location[1:])
                material_file = GeneratedMaterial(
                    id=start_index,
                    png_width=img.width,
                    png_height=img.height,
                    index=job_number,
                    png_file_path=saved_location,
                    job_id=job_number,
                    element_id=element.id,
                    element_name=element.name,
                    element=element,
                    font_name=font_name,
                    color=color,
                )
                result_list.append(material_file)
            start_index -= 1

    return result_list


def randomly_choose_text(generated_materials: t.List[GeneratedMaterial], registered_materials_from_db):
    black = "black"
    other = "other"
    db_item = "db_item"
    material_map = {
        black: [],
        other: [],
    }

    for item in generated_materials:
        if "#000000".lower() in str(item.png_file_path).lower():
            material_map[black].append(item)
        else:
            material_map[other].append(item)
    if registered_materials_from_db:
        material_map[db_item] = []
        for each_item in registered_materials_from_db:
            material_map[db_item].append(each_item)
    item_list = []
    item_weight = []
    if registered_materials_from_db:
        item_list.extend([black, other, db_item])
        item_weight.extend([0.7 * 1 / 3, 0.3 * 1 / 3, 1 / 3])
    else:
        item_list.extend([black, other])
        item_weight.extend([0.7, 0.3])

    chosen_item: GeneratedMaterial = random.choices(item_list, weights=item_weight)[0]
    chosen_value: GeneratedMaterial = random.choice(material_map[chosen_item])

    return chosen_value


def get_font_and_color(ids, titles):
    font, color = None, None
    for id in ids:
        for title in titles:
            if not isinstance(title, GeneratedMaterial):
                continue
            if id == title.id:
                font, color = title.font_name, title.color
                break
        if font is not None:
            break
    return font or "", color or ""