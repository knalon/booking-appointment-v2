import React,{useEffect,useRef} from 'react';
export default function EditorDialog({children,onClose}){
 const ref=useRef(null);
 useEffect(()=>{const d=ref.current;d.showModal();return()=>{if(d.open)d.close()}},[]);
 return <dialog ref={ref} className="editor-dialog" aria-label="Edit faculty record" onCancel={e=>{e.preventDefault();onClose()}}>{children}</dialog>;
}
