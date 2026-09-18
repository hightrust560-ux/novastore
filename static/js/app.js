async function api(url, data){
  const res = await fetch(url,{method:"POST",headers:{"Content-Type":"application/json","X-Requested-With":"XMLHttpRequest","X-CSRFToken":document.querySelector("meta[name=csrf-token]")?.content || ""},body:JSON.stringify(data)});
  const json = await res.json();
  if(!res.ok || !json.ok) throw new Error(json.message || "Request failed");
  return json;
}
function updateBadges(data){
  document.querySelectorAll(".cart-count").forEach(x=>x.textContent=data.cart_count ?? x.textContent);
  document.querySelectorAll(".wishlist-count").forEach(x=>x.textContent=data.wishlist_count ?? x.textContent);
}
document.addEventListener("click", async e=>{
  const add=e.target.closest(".add-cart");
  if(add){
    e.preventDefault();
    const qtyInput=document.getElementById("qty");
    const quantity=qtyInput ? Number(qtyInput.value||1) : 1;
    try{const data=await api("/api/cart/add",{product_id:Number(add.dataset.productId),quantity});updateBadges(data);add.textContent="Added ✓";setTimeout(()=>add.textContent="Add to cart",1200);}
    catch(err){alert(err.message)}
  }
  const wish=e.target.closest(".wishlist-toggle");
  if(wish){
    e.preventDefault();
    try{const data=await api("/api/wishlist/toggle",{product_id:Number(wish.dataset.productId)});updateBadges(data);wish.textContent=data.active?"♥ Saved":"♡ Wishlist";}
    catch(err){alert(err.message)}
  }
  const remove=e.target.closest(".cart-remove");
  if(remove){
    try{const data=await api("/api/cart/remove",{product_id:Number(remove.dataset.productId)});updateBadges(data);location.reload();}
    catch(err){alert(err.message)}
  }
  const plus=e.target.closest(".cart-plus");
  if(plus){
    const row=plus.closest(".cart-item"); const span=row.querySelector(".qty-control span"); const qty=Number(span.textContent)+1; const max=Number(plus.dataset.max);
    if(qty<=max){try{await api("/api/cart/update",{product_id:Number(plus.dataset.productId),quantity:qty});location.reload()}catch(err){alert(err.message)}}
  }
  const minus=e.target.closest(".cart-minus");
  if(minus){
    const row=minus.closest(".cart-item"); const span=row.querySelector(".qty-control span"); const qty=Number(span.textContent)-1;
    try{await api("/api/cart/update",{product_id:Number(minus.dataset.productId),quantity:qty});location.reload()}catch(err){alert(err.message)}
  }
});
document.addEventListener("DOMContentLoaded",()=>{
  const slides=[...document.querySelectorAll(".hero-slide")];
  if(slides.length>1){let i=0;setInterval(()=>{slides[i].classList.remove("active");i=(i+1)%slides.length;slides[i].classList.add("active")},6000)}
});
