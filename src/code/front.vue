<template>
    <div class="wrapper label-title">
        <div class="description prod-title">{{ title }}</div>
        <div class="px-12"></div>
        <div class="wrapper">
            <div class="left-area">
                <div class="input-area">
                    <textarea v-model="inputText" maxlength="30" type="text" placeholder="" class="input content" rows="5"
                        @input="update_content"></textarea>
                    <p>30文字以内で記入してください。改行は反映されます。</p>
                </div>
                <div class="min-area">
                    <p>文字の向き</p>
                    <input :id="'tate' + identifier" v-model="textDirection" type="radio"
                        :name="'text-direction-' + identifier" value=1 checked><label class="ml-5 mr-5"
                        :for="'tate' + identifier">縦書き</label>
                    <input :id="'yoko' + identifier" v-model="textDirection" class="ml-10" type="radio"
                        :name="'text-direction-' + identifier" value=0><label class="ml-5 mr-5"
                        :for="'yoko' + identifier">横書き</label>
                </div>
                <div class="buttons">
                    <button class="pale-button-negative button-wrapper" @click="reset">設定をリセット</button>
                    <button class="pale-button-positive button-wrapper" @click="generate">プレビュー生成</button>
                </div>
            </div>
            <div class="right-area">
                <div class="title">プレビュー ※文字色と書体は、生成時に自動でランダムに選ばれます</div>
                <div class="image-wrapper">
                    <img v-if="imageSrc" :src="imageSrc" alt="preview image">
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { mapActions } from 'vuex'
export default {
    props: {
        title: {
            type: String,
            required: true,
        },
        identifier: {
            type: String,
            required: true,
        },
        default_text: {
            type: String,
            required: false,
            default: '',
        },
        default_radio: {
            type: Number,
            required: false,
            default: 1,
        },
    },
    data() {
        return {
            inputText: this.default_text,
            textDirection: this.default_radio,
            imageSrc: '',
        }
    },
    watch: {
        textDirection() {
            this.update_content();
        },
        default_text(newVal) {
            this.inputText = newVal
        },
        default_radio(newVal) {
            this.textDirection = newVal
        },
    },
    methods: {
        ...mapActions('jobs', ['preview_text_to_image']),
        reset() {
            this.inputText = '';
            this.textDirection = 1;
            this.imageSrc = '';
        },
        update_content() {
            this.$emit('textChanged', {
                text: this.inputText,
                is_vertical: parseInt(this.textDirection),
                identifier: this.identifier,
            })
        },
        generate() {
            this.preview_text_to_image({
                data: {
                    text: this.inputText,
                    font_path: 'your_font_path_here',
                    is_vertical: this.textDirection,
                },
            }).then(res => {
                this.imageSrc = res
            })
                .catch(err => {
                    console.log(err)
                })
        },
    },
}
</script>
