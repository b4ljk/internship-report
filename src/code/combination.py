def create_combination_materials(db: Session, job_id: int, label_generation_number: int, layout_pattern_number: int):
    job = crud.jobs.get(db=db, id=job_id)
    materials = []
    info_materials = None

    # text to image process
    start_time = time.time()

    title_chosen: List[GeneratedMaterial] = []
    copy_chosen: List[GeneratedMaterial] = []

    generated_titles: List[GeneratedMaterial] = []
    generated_copies: List[GeneratedMaterial] = []
    registered_titles_from_db: List[RegisteredMaterials] = []
    registered_copies_from_db: List[RegisteredMaterials] = []

    unique_pattern_num = label_generation_number // layout_pattern_number

    if job.text_title_string:
        registered_titles_from_db = crud.registered_materials.search_registered_material_by_text(
            db=db, text=job.text_title_string
        )
        title_elm = crud.labels.get_by_name(db=db, name="text_title")
        generated_titles = pillow_text_generator(
            text=job.text_title_string,
            is_vertical=bool(job.text_title_is_vertical),
            job_number=job_id,
            text_type="text_title",
            element=title_elm,
        )

    if job.text_copy_string:
        registered_copies_from_db = crud.registered_materials.search_registered_material_by_text(
            db=db, text=job.text_copy_string
        )
        copy_elm = crud.labels.get_by_name(db=db, name="text_copy")
        generated_copies = pillow_text_generator(
            text=job.text_copy_string,
            is_vertical=bool(job.text_copy_is_vertical),
            text_type="text_copy",
            job_number=job_id,
            element=copy_elm,
        )

    logging.info("--- execution time to text to image: %s seconds ---" % (time.time() - start_time))

    if job.job_type == 0:
        materials = crud.materials.get_multi_by_job_id(db=db, job_id=job_id)
    elif job.job_type == 1:
        # execution start time
        start_time = time.time()

        # Get materials from tag ids
        job_tags: List[TagList] = []
        tag_id_records = crud.input_tag_record.get_multi_job_id(db=db, job_id=job.id)
        for tag_id_record in tag_id_records:
            tag = crud.tags.get(db=db, id=tag_id_record.tag_list_id)
            job_tags.append(tag)
        recommended_tags = crud.recommended_tag_record.get_multi_job_id(db=db, job_id=job.id)
        for tag_id_record in recommended_tags:
            tag = crud.tags.get(db=db, id=tag_id_record.tag_list_id)
            job_tags.append(tag)

        logging.info({"Combination tag ids": job_tags})
        tag_material_relations: List[TagMaterialRelation] = []
        for tag_id in job_tags:
            tag_material_relation = crud.tag_material_relation.get_multi_by_tag_id(db=db, tag_id=tag_id.id)
            tag_material_relations = tag_material_relations + tag_material_relation
        for tag_material_relation in tag_material_relations:
            material = crud.registered_materials.get(db=db, id=tag_material_relation.registered_material_id)
            materials.append(material)

        # Exclude duplicates
        materials = list(set(materials))

        logging.info("--- execution time to fetch materials by tag: %s seconds ---" % (time.time() - start_time))
        for material in materials:
            logging.info(
                [
                    material.id,
                    material.element.name,
                    [[tag.tag_list.tag_types.name, tag.tag_list.name] for tag in material.tag_material_relation],
                ]
            )

        # Filter materials by tag relevancy
        start_time = time.time()
        materials = filter_materials_by_tag(materials, job_tags)
        logging.info("--- execution time to filter materials by tags: %s seconds ---" % (time.time() - start_time))

        # execution start time
        start_time = time.time()

        # Get info materials
        info_materials = get_info_materials(db=db, job=job)
        materials += info_materials

        logging.info({"materials before pixta": len(materials)})

        # Get images from pixta
        keywords = extract_keywords(job.text_title_string)
        pixta_back_images = get_images(db=db, job_id=job.id, keywords=keywords, is_background=True)
        pixta_main_images = get_images(db=db, job_id=job.id, keywords=keywords)
        materials += pixta_back_images
        materials += pixta_main_images

        logging.info({"last material": materials[-1]})
        if job.text_title_string:
            materials = [material for material in materials if material.element_id != title_elm.id]

        if job.text_copy_string:
            materials = [material for material in materials if material.element_id != copy_elm.id]

        logging.info({"materials count": len(materials)})

        logging.info("--- execution time to fetch material infos: %s seconds ---" % (time.time() - start_time))

        # execution start time
        start_time = time.time()

        logging.info([job_id, [[tag.tag_types.name, tag.name] for tag in job_tags]])
        for material in materials:
            if material.id < 0:
                continue
            logging.info(
                [
                    material.id,
                    material.element.name,
                    [[tag.tag_list.tag_types.name, tag.tag_list.name] for tag in material.tag_material_relation],
                ]
            )

        logging.info({"Combination materials: ": materials})
        if len(materials) < 1:
            return
        # Index materials in one label
        materials_indexed = []
        label_map = {}
        for material in materials:
            if material.element.name in label_map:
                label_map[material.element.name].append(material.__dict__)
            else:
                label_map[material.element.name] = [material.__dict__]

        for value in label_map.values():
            for idx, item in enumerate(value):
                value[idx] = {**item, "index": idx + 1}
            materials_indexed += value

        logging.info("--- execution time to index materials in one label: %s seconds ---" % (time.time() - start_time))
        logging.info({"materials_indexed": materials_indexed})
        # execution start time
        start_time = time.time()

        # Copy material pngs to job input folder
        png_folder = f"/static/jobs/{job_id}/input/png"
        create_folder(png_folder)
        for material in materials_indexed:
            if material["id"] < -12:
                continue
            file_name = f"{material['element'].name}_{material['index']}.png"
            file_path = os.path.join(png_folder, file_name)

            if not settings.IS_LOCAL:
                try:
                    s3 = boto3.resource("s3")
                    copy_source = {
                        "Bucket": bucket_name,
                        "Key": material["png_file_path"][1:],
                    }
                    bucket = s3.Bucket(bucket_name)
                    s3_file_key = file_path[1:]
                    bucket.copy(copy_source, s3_file_key)
                except Exception as e:
                    logging.info({"back png s3 copy exception": e})
            else:
                shutil.copy2(material["png_file_path"], file_path)

            material["png_file_path"] = file_path

        logging.info("--- execution time to copy materials: %s seconds ---" % (time.time() - start_time))

        if not settings.IS_LOCAL:
            os.rmdir(png_folder)

    # execution start time
    start_time = time.time()

    comb_map = {}
    align_map = {}
    for r in materials:
        if r.png_height > r.png_width:
            align_map[r.id] = False
        else:
            align_map[r.id] = True

        if r.element_id in comb_map:
            comb_map[r.element_id].append(r.id)
        else:
            comb_map[r.element_id] = [r.id]
    logging.info(comb_map)

    values = []
    for i in sorted(comb_map):
        values.append(comb_map[i][-10:])

    logging.info(values)
    material_combs = []
    max_combo_num = label_generation_number // layout_pattern_number + (
        label_generation_number % layout_pattern_number > 0
    )
    for _ in range(max_combo_num):
        random_title: GeneratedMaterial = None
        random_copy: GeneratedMaterial = None
        if job.text_title_string:
            random_title = randomly_choose_text(
                generated_materials=generated_titles, registered_materials_from_db=registered_titles_from_db
            )
            title_chosen.append(random_title)
            materials_indexed += [random_title.__dict__]
        if job.text_copy_string:
            random_copy = randomly_choose_text(
                generated_materials=generated_copies, registered_materials_from_db=registered_copies_from_db
            )
            copy_chosen.append(random_copy)
            materials_indexed += [random_copy.__dict__]

        material_combs.append((random_product(*values, chosen_title=random_title, chosen_copy=random_copy)))

    logging.info({"comb_map": comb_map})
    logging.info({"material_combs": material_combs})
    logging.info({"len material_combs": len(material_combs)})

    # execution start time
    start_time = time.time()

    labels = []
    for matid in material_combs[0]:
        if job.job_type == 0:
            mat = crud.materials.get(db=db, id=matid)
            labels.append(mat.element.name)
        elif job.job_type == 1:
            mat = crud.registered_materials.get(db=db, id=matid)
            if mat is None:
                continue
            labels.append(mat.element.name)
    if info_materials is not None:
        labels += [x.element.name for x in info_materials]
    logging.info({"labels": labels})

    if ("info_barcode" in labels) and ("text_title" in labels):
        tmp_mat_comb = []
        barcode_idx = labels.index("info_barcode")
        text_title_idx = labels.index("text_title")
        for comb in material_combs:
            text_long_width_flag = True
            barcode_long_width_flag = True
            # for matid in comb:
            #     mat = crud.materials.get(db=db, id=matid)
            #     if mat.label.name == "text_title":
            #         if mat.height > mat.width:
            #             text_long_width_flag = False
            #     if mat.label.name == "info_barcode":
            #         if mat.height > mat.width:
            #             barcode_long_width_flag = False
            barcode_matid = comb[barcode_idx]
            barcode_long_width_flag = align_map[barcode_matid]
            text_title_matid = comb[text_title_idx]
            text_long_width_flag = align_map[text_title_matid]
            if barcode_long_width_flag == text_long_width_flag:
                tmp_mat_comb.append(comb)
        material_combs = tmp_mat_comb

    # logging.info({"after barcode material_combs": material_combs})
    logging.info({"after barcode len material_combs": len(material_combs)})

    tmp_aligned_comb = []
    tmp_not_aligned_comb = []
    labels_to_align = ["text_title", "text_copy", "text_explain"]
    active_labels_to_align = [lab for lab in labels_to_align if lab in labels]
    active_labels_idx = [labels.index(lab) for lab in active_labels_to_align]
    if len(active_labels_to_align) > 1:
        for comb in material_combs:
            rule_align_flags = []
            for actv_idx in active_labels_idx:
                matid = comb[actv_idx]
                rule_align_flags.append(align_map[matid])
            # for matid in comb:
            # mat = crud.materials.get(db=db, id=matid)
            # if mat.label.name in active_labels_to_align:
            #     if mat.height > mat.width:
            #         rule_align_flags.append(False)
            #     else:
            #         rule_align_flags.append(True)
            if (sum(rule_align_flags) == 0) or (sum(rule_align_flags) == len(active_labels_to_align)):
                tmp_aligned_comb.append(comb)
            else:
                tmp_not_aligned_comb.append(comb)
    else:
        tmp_aligned_comb = material_combs
        tmp_not_aligned_comb = []

    # logging.info({"tmp_aligned_comb": tmp_aligned_comb})
    # logging.info({"tmp_not_aligned_comb": tmp_not_aligned_comb})
    logging.info({"len tmp_aligned_comb": len(tmp_aligned_comb)})
    logging.info({"len tmp_not_aligned_comb": len(tmp_not_aligned_comb)})

    aligned_rate = 1
    aligned_num = int(label_generation_number * aligned_rate)

    if len(tmp_aligned_comb) > aligned_num:
        tmp_aligned_comb = random.sample(tmp_aligned_comb, aligned_num)
    tmp_not_aligned_comb = random.sample(tmp_not_aligned_comb, len(tmp_not_aligned_comb))
    tmp_aligned_comb.extend(tmp_not_aligned_comb)

    material_combs = tmp_aligned_comb[:label_generation_number]
    logging.info({"last material_combs": material_combs})

    limit = min(len(material_combs), 100)
    # rounding up the division if there is a remainder
    combinations = [f"random_{i}" for i in range(1, limit + 1)]

    for comb, mc in zip(combinations, material_combs):
        # material combo dotor bga title copy 2g avaad font-g ni job combosruu hadgalnaa
        text_title_font, text_title_color = "", ""
        copy_font, copy_color = "", ""

        if job.text_title_string:
            text_title_font, text_title_color = get_font_and_color(mc, title_chosen)

        if job.text_copy_string:
            copy_font, copy_color = get_font_and_color(mc, copy_chosen)

        jc_in = schemas.JobCombinationsCreate(
            job_id=job_id,
            comb_name=comb,
            text_title_font=text_title_font,
            text_title_color=text_title_color,
            text_copy_font=copy_font,
            text_copy_color=copy_color,
        )
        crud.job_combinations.create(db=db, obj_in=jc_in)

    job_combs = crud.job_combinations.get_multi_job_id(db=db, job_id=job_id)

    data = []
    combinations = []

    for jc, material_ids in zip(job_combs, material_combs):
        combination_materials = []
        for material_id in material_ids:
            if job.job_type == 0:
                data.append(JobCombinationMaterials(job_comb_id=jc.id, material_uploaded_id=material_id))
            elif job.job_type == 1:
                if material_id > 0:
                    data.append(JobCombinationMaterialsSelected(job_comb_id=jc.id, registered_material_id=material_id))

                # Return indexed materials

                material = list(filter(lambda x: x["id"] == material_id, materials_indexed))[0]

                combination_material_data = (
                    jc.id,
                    material["png_width"],
                    material["png_height"],
                    material["element"].name,
                    material["png_file_path"],
                    material["index"],
                )
                combination_materials.append(combination_material_data)

        combinations.append((combination_materials, jc.id))

    db.bulk_save_objects(data)
    db.commit()

    logging.info("--- execution time to create combs: %s seconds ---" % (time.time() - start_time))

    return combinations if job.job_type == 1 else None
