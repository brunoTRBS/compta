drop policy "owner_only" on "public"."account_balance_history";

drop policy "owner_only" on "public"."accounts";

drop policy "owner_only" on "public"."categories";

drop policy "owner_only" on "public"."categorization_rules";

drop policy "owner_only" on "public"."stripe_transactions";

drop policy "owner_only" on "public"."transactions";

grant select on table "public"."account_balance_history" to "app_reader";

grant select on table "public"."accounts" to "app_reader";

grant select on table "public"."categories" to "app_reader";

grant select on table "public"."categorization_rules" to "app_reader";

grant select on table "public"."stripe_transactions" to "app_reader";

grant select on table "public"."transactions" to "app_reader";

grant select on table "public"."urssaf_rates" to "app_reader";


  create policy "owner_only"
  on "public"."account_balance_history"
  as permissive
  for all
  to public
using ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])))
with check ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])));



  create policy "owner_only"
  on "public"."accounts"
  as permissive
  for all
  to public
using ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])))
with check ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])));



  create policy "owner_only"
  on "public"."categories"
  as permissive
  for all
  to public
using ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])))
with check ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])));



  create policy "owner_only"
  on "public"."categorization_rules"
  as permissive
  for all
  to public
using ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])))
with check ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])));



  create policy "owner_only"
  on "public"."stripe_transactions"
  as permissive
  for all
  to public
using ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])))
with check ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])));



  create policy "owner_only"
  on "public"."transactions"
  as permissive
  for all
  to public
using ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])))
with check ((auth.uid() = ANY (ARRAY['f6856b4b-50ce-44bb-b4a7-702513db2577'::uuid, 'ecd32d6a-0d59-4185-b516-4f9f01b62525'::uuid])));



