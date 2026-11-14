// Rebuild page-level corpus from original PDFs. Requires Poppler, Tesseract and vie data.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
process.chdir(path.resolve(__dirname, '..'));
const poppler = process.env.POPPLER_BIN || 'C:/poppler-24.08.0/Library/bin';
const tesseract = process.env.TESSERACT_EXE || 'C:/Program Files/Tesseract-OCR/tesseract.exe';
function run(exe, args) {
  const r = spawnSync(exe, args, {encoding:'utf8', windowsHide:true, maxBuffer:16*1024*1024});
  if(r.status !== 0) throw new Error(`${exe}: ${r.error || r.stderr}`);
  return r.stdout;
}
function write(file, text) { fs.mkdirSync(path.dirname(file), {recursive:true}); fs.writeFileSync(file, text); }
function hash(file) {return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');}
const docs = [
  {source_id:'luat-24-2018-qh14', title:'Luật An ninh mạng', number:'24/2018/QH14', year:2018, doc_type:'Luật', issued_at:'2018-06-12', effective_date_as_issued:'2019-01-01', source_path_or_url:'https://vanban.chinhphu.vn/?pageid=27160&docid=206114', download_url:'https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/07/24-2018-qh14..pdf', local_path:'data/raw/24-2018-qh14.pdf', prefix:'24-2018-qh14', physical_pages:32, content_end:32, extraction:'pdftotext-layout'},
  {source_id:'nghi-dinh-13-2023-nd-cp', title:'Nghị định về bảo vệ dữ liệu cá nhân', number:'13/2023/NĐ-CP', year:2023, doc_type:'Nghị định', issued_at:'2023-04-17', effective_date_as_issued:'2023-07-01', source_path_or_url:'https://vanban.chinhphu.vn/?pageid=27160&docid=207759', download_url:'https://datafiles.chinhphu.vn/cpp/files/vbpq/2023/4/13nd.signed.pdf', local_path:'data/raw/13-2023-nd-cp.pdf', prefix:'13-2023-nd-cp', physical_pages:39, content_end:28, extraction:'tesseract-vie-200dpi-psm3'}
];
const pages = [];
fs.mkdirSync('tmp/corpus', {recursive:true});
for(const d of docs) {
  let texts;
  if(d.extraction.startsWith('pdftotext')) {
    run(path.join(poppler,'pdftotext.exe'), ['-layout',d.local_path,`tmp/corpus/${d.prefix}.raw.txt`]);
    texts=fs.readFileSync(`tmp/corpus/${d.prefix}.raw.txt`,'utf8').split('\f').slice(0,d.physical_pages);
  } else {
    texts=[];
    for(let p=1;p<=d.physical_pages;p++) {
      const base=`tmp/corpus/ocr/${d.prefix}-${String(p).padStart(3,'0')}`;
      if(!fs.existsSync(base+'.txt')) {
        fs.mkdirSync('tmp/pdfs',{recursive:true});
        run(path.join(poppler,'pdftoppm.exe'),['-f',String(p),'-l',String(p),'-r','200','-singlefile','-png',d.local_path,'tmp/pdfs/ocr-page']);
        fs.mkdirSync(path.dirname(base),{recursive:true});
        run(tesseract,['tmp/pdfs/ocr-page.png',base,'--tessdata-dir','tmp/corpus/tessdata','-l','vie','--psm','3']);
      }
      texts.push(fs.readFileSync(base+'.txt','utf8'));
      console.log(`OCR ${p}/${d.physical_pages}`);
    }
    write(`tmp/corpus/${d.prefix}.raw.txt`,texts.join('\f'));
  }
  let docPages=[];
  texts.forEach((raw,i)=>{
    const page=i+1;
    // Keep paragraph/line structure and legal numbering. Remove only known law headers/signature stamp.
    let text=raw.normalize('NFC').replace(/\r/g,'').split('\n').filter(line=>{
      if(d.year!==2018) return true;
      return !/CÔNG BÁO\/Số 775 \+ 776\/Ngày 14-7-2018|^\s*(Ký bởi:|Email: thongtinchinhphu|Cơ quan: Văn phòng Chính phủ|Thời gian ký:)/u.test(line);
    }).map(l=>l.replace(/[\t \u00a0]+/g,' ').trim()).join('\n').replace(/\n{3,}/g,'\n\n').trim();
    const item={document_id:d.source_id,source:d.local_path,page,page_id:`${d.source_id}:p${String(page).padStart(3,'0')}`,text,metadata:{doc_type:d.doc_type,year:d.year,language:'vi',document_number:d.number,source_url:d.source_path_or_url,extraction_method:d.extraction,ocr_review_status:d.year===2023?'sample_checked_not_fully_corrected':'not_applicable',included_in_corpus:page<=d.content_end},char_count:[...text].length};
    docPages.push(item);
    if(item.metadata.included_in_corpus) pages.push(item);
  });
  d.sha256=hash(d.local_path);
  d.accessed_at=fs.statSync(d.local_path).mtime.toISOString();
  d.license_or_permission='Văn bản quy phạm pháp luật: không thuộc phạm vi bảo hộ quyền tác giả theo khoản 2 Điều 15 Luật Sở hữu trí tuệ. Ghi nguồn Cổng TTĐT Chính phủ; không áp dụng cho nội dung biên tập/thiết kế website.';
  d.license_basis_url='https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/9/46214/58977-1-20251383-1384155-vbhn-vpqh.pdf';
  d.legal_status='original_historical_snapshot_current_validity_not_assessed';
  d.included_pages=docPages.filter(x=>x.metadata.included_in_corpus).map(x=>x.page);
  d.excluded_pages=docPages.filter(x=>!x.metadata.included_in_corpus).map(x=>({page:x.page,reason:'Phụ lục/biểu mẫu, giữ nguyên bản gốc nhưng không tính vào corpus chính.'}));
  d.page_character_counts=docPages.map(x=>({page:x.page,characters:x.char_count,included:x.metadata.included_in_corpus}));
  d.normalized_characters=docPages.filter(x=>x.metadata.included_in_corpus).reduce((n,x)=>n+x.char_count,0);
}
write('data/processed/corpus.pages.jsonl',pages.map(x=>JSON.stringify(x)).join('\n')+'\n');
const manifest={topic:'An ninh mạng và bảo vệ dữ liệu cá nhân tại Việt Nam',snapshot_policy:'Hai văn bản gốc theo năm ban hành, không phải bộ pháp luật hợp nhất/cập nhật hiện hành.',page_numbering:'page là số trang vật lý PDF tính từ 1, không phải số trang in Công báo.',counting_rule:'Tính 32 trang Luật và 28 trang nội dung chính Nghị định. Loại 11 trang phụ lục/biểu mẫu Nghị định khỏi corpus chính. Không nhân bản hoặc tái phân trang.',content_pages:pages.length,normalized_characters:pages.reduce((n,x)=>n+x.char_count,0),metadata_schema:{doc_type:'string: Luật | Nghị định; từ loại văn bản tại nguồn',year:'integer: 2018 | 2023; năm ban hành, không phải năm hiệu lực',language:'string: vi'},limitations:['OCR Nghị định chưa được hiệu đính toàn văn; đối chiếu PDF trước khi lấy gold evidence.','Hai trường doc_type và year tương quan hoàn toàn trong corpus hai văn bản; không suy ra tác động độc lập của từng trường.','Không khẳng định hiệu lực pháp lý hiện tại của các bản gốc.'],documents:docs};
write('data/manifest.json',JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({pages:pages.length,characters:manifest.normalized_characters}));
