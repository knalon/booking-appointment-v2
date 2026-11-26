let csrf='';
export async function request(path,options={}){
 const headers={...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(csrf?{'X-CSRFToken':csrf}:{}),...options.headers};
 const res=await fetch(path,{credentials:'same-origin',...options,headers});
 if(res.ok&&options.download)return res.blob();
 let data;try{data=await res.json()}catch{throw new Error('Unexpected server response. Check Django and refresh.');}
 if(!res.ok){const err=new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data));err.data=data;err.status=res.status;throw err;}
 if(data.csrfToken)csrf=data.csrfToken;return data;
}
export const api=(path,opts)=>request('/api/directory/'+path,opts);
