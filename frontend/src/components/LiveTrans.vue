<template>
    <div>
        <b-button block @click="getMessage()">Or, Click here to translate Live!</b-button>
        <samp>{{ msg }}</samp>
    </div>
</template>

<script>
import axios from 'axios-observable';
export default {
  
  name: 'LiveTrans',
  props: ['response'],
  data: () => {
    return { 
        msg: ''
    }
  },
  methods: {
      getMessage() {
      axios.defaults.headers.common['Content-Type'] = 'text/html'
      axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';
      const path = 'http://localhost:3000/LiveTrans';
      console.log('in method')
      axios.get(path).subscribe((res) => {
          console.log(res)
          this.msg = res.data;
          this.msg = JSON.parse('server\\routes\\spchToTxtLive.json')
        })
        
        // .catch((error) => {
        //   // eslint-disable-next-line
        //   console.error(error);
        // });
    },
  },
  created() {
    console.log('in created')
    this.getMessage();}
}
</script>

<style>
.dropzone {
    background-color: #000;
    border-radius: 8px;
    height: 400px;
}
.vue-dropzone {
    border: none;
    color: rgb(193, 193, 193);
}
.upload-icon {
    width:96px;
    margin-top: 80px
}
</style>

